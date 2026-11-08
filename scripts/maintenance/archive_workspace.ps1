[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Capture', 'Verify')][string]$Action,
    [Parameter(Mandatory)][string]$ArchiveRoot,
    [string]$SourceRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$env:GIT_OPTIONAL_LOCKS = '0'
$env:GIT_TERMINAL_PROMPT = '0'
$schema = 'workspace-retirement/1'
$userSid = [Security.Principal.WindowsIdentity]::GetCurrent().User
$allowedSids = @($userSid.Value, 'S-1-5-18')

function Get-SafeRoot([string]$Path) {
    if (-not [IO.Path]::IsPathFullyQualified($Path)) { throw 'An absolute path is required.' }
    $full = [IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
    if ($full -eq [IO.Path]::GetPathRoot($full).TrimEnd('\', '/')) {
        throw 'A volume root is not a workspace.'
    }
    $cursor = $full
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'Reparse roots and ancestors are forbidden.'
            }
            if (-not $item.PSIsContainer) { throw 'A path ancestor is not a directory.' }
        }
        $parent = [IO.Directory]::GetParent($cursor)
        $cursor = if ($parent) { $parent.FullName } else { $null }
    }
    return $full
}

function Assert-OutsideGit([string]$Path) {
    $cursor = $Path
    while ($cursor) {
        if (Test-Path -LiteralPath (Join-Path $cursor '.git')) {
            throw 'The archive must be outside code repositories.'
        }
        $parent = [IO.Directory]::GetParent($cursor)
        $cursor = if ($parent) { $parent.FullName } else { $null }
    }
}

function Assert-SeparateRoots([string]$Source, [string]$Archive) {
    $comparison = [StringComparison]::OrdinalIgnoreCase
    if ($Source.Equals($Archive, $comparison) -or
        $Archive.StartsWith($Source + '\', $comparison) -or
        $Source.StartsWith($Archive + '\', $comparison)) {
        throw 'Source and archive must be disjoint.'
    }
}

function Set-PrivateRoot([string]$Path) {
    $acl = [Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.SetOwner($userSid)
    foreach ($sid in $allowedSids) {
        $identity = [Security.Principal.SecurityIdentifier]::new($sid)
        $rule = [Security.AccessControl.FileSystemAccessRule]::new(
            $identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Assert-PrivateAccess([IO.FileSystemInfo]$Item) {
    $acl = [IO.FileSystemAclExtensions]::GetAccessControl(
        $Item, [Security.AccessControl.AccessControlSections]::Access)
    foreach ($rule in $acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier])) {
        if ($rule.AccessControlType -eq 'Allow' -and
            $rule.IdentityReference.Value -notin $allowedSids) {
            throw 'Archive access is broader than owner and SYSTEM.'
        }
    }
}

function Get-Hash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    try {
        return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($stream)).ToLowerInvariant()
    } finally { $stream.Dispose() }
}

function Write-Json([string]$Path, $Value) {
    [IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 12),
        [Text.UTF8Encoding]::new($false))
}

function Get-Inventory([string]$Root, [switch]$Private) {
    $files = [Collections.Generic.List[object]]::new()
    $directories = [Collections.Generic.List[string]]::new()
    $links = [Collections.Generic.List[object]]::new()
    $pending = [Collections.Generic.Stack[IO.DirectoryInfo]]::new()
    $pending.Push([IO.DirectoryInfo]::new($Root))
    [long]$totalBytes = 0
    while ($pending.Count -gt 0) {
        $directory = $pending.Pop()
        if ($Private) { Assert-PrivateAccess $directory }
        foreach ($entry in $directory.EnumerateFileSystemInfos()) {
            $relative = [IO.Path]::GetRelativePath($Root, $entry.FullName).Replace('\', '/')
            if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                $link = Get-Item -LiteralPath $entry.FullName -Force
                $links.Add([pscustomobject]@{
                    path = $relative; type = $link.LinkType; targets = @($link.Target)
                    directory = (($entry.Attributes -band [IO.FileAttributes]::Directory) -ne 0)
                })
                continue
            }
            if ($entry -is [IO.DirectoryInfo]) {
                $directories.Add($relative)
                $pending.Push($entry)
                continue
            }
            if ($Private) { Assert-PrivateAccess $entry }
            $length = $entry.Length
            $modified = $entry.LastWriteTimeUtc
            $hash = Get-Hash $entry.FullName
            $entry.Refresh()
            if ($length -ne $entry.Length -or $modified -ne $entry.LastWriteTimeUtc) {
                throw 'A file changed while hashing.'
            }
            $totalBytes += $length
            $files.Add([pscustomobject]@{
                path = $relative; bytes = $length; sha256 = $hash
                lastWriteTimeUtc = $modified.ToString('o')
            })
        }
    }
    return [pscustomobject]@{
        schema = $schema; files = $files.ToArray(); directories = $directories.ToArray()
        links = $links.ToArray(); fileCount = $files.Count; totalBytes = $totalBytes
    }
}

function Assert-MatchingInventory($Expected, $Actual, [switch]$Snapshot) {
    if ($Expected.fileCount -ne $Actual.fileCount -or
        $Expected.totalBytes -ne $Actual.totalBytes -or
        $Expected.directories.Count -ne $Actual.directories.Count) {
        throw 'Workspace file, byte or directory count mismatch.'
    }
    $files = [Collections.Generic.Dictionary[string, object]]::new([StringComparer]::Ordinal)
    foreach ($file in $Expected.files) { $files.Add($file.path, $file) }
    foreach ($file in $Actual.files) {
        if (-not $files.ContainsKey($file.path)) { throw 'Unexpected payload file.' }
        $wanted = $files[$file.path]
        if ($wanted.bytes -ne $file.bytes -or $wanted.sha256 -ne $file.sha256) {
            throw 'Payload bytes do not match the captured inventory.'
        }
    }
    $directories = [Collections.Generic.HashSet[string]]::new(
        [string[]]$Expected.directories, [StringComparer]::Ordinal)
    if (-not $directories.SetEquals([string[]]$Actual.directories)) {
        throw 'Directory inventory mismatch.'
    }
    if ($Snapshot) {
        if ($Actual.links.Count -ne 0) { throw 'An archive snapshot contains a live link.' }
    } else {
        $expectedLinks = @($Expected.links | Sort-Object path) | ConvertTo-Json -Depth 6 -Compress
        $actualLinks = @($Actual.links | Sort-Object path) | ConvertTo-Json -Depth 6 -Compress
        if ($expectedLinks -ne $actualLinks) { throw 'Source link inventory changed.' }
    }
}

function Invoke-Git([string]$Root, [string[]]$Arguments) {
    $output = @(& git -C $Root -c core.fsmonitor=false -c core.hooksPath=NUL @Arguments 2>&1)
    if ($LASTEXITCODE -ne 0) { throw 'A local Git integrity operation failed.' }
    return @($output | ForEach-Object { $_.ToString() })
}

function Get-GitState([string]$Root) {
    return [pscustomobject]@{
        head = (Invoke-Git $Root @('rev-parse', 'HEAD')) -join ''
        refs = @(Invoke-Git $Root @('for-each-ref', '--format=%(refname) %(objectname)'))
        status = @(Invoke-Git $Root @('status', '--porcelain=v1', '--untracked-files=all'))
    }
}

function Assert-StandaloneGit([string]$Root) {
    $git = Join-Path $Root '.git'
    if (-not (Test-Path -LiteralPath $git -PathType Container)) {
        throw 'A standalone Git working directory is required.'
    }
    foreach ($relative in @('commondir', 'objects/info/alternates', 'worktrees')) {
        if (Test-Path -LiteralPath (Join-Path $git $relative)) {
            throw 'Externally shared Git storage requires a separate migration.'
        }
    }
    $configured = @(& git -C $Root config --local --get core.worktree 2>$null)
    if ($configured.Count -gt 0) { throw 'External Git worktree configuration is unsupported.' }
    $null = Get-SafeRoot $git
}

function Assert-ArchiveSurface([string]$Root) {
    $allowed = @('snapshot', 'inventory.json', 'capture.json', 'history.bundle', 'evidence')
    $pending = [Collections.Generic.Stack[IO.FileSystemInfo]]::new()
    $directory = [IO.DirectoryInfo]::new($Root)
    Assert-PrivateAccess $directory
    foreach ($entry in $directory.EnumerateFileSystemInfos()) {
        if ($entry.Name -notin $allowed) { throw 'Unexpected archive-root entry.' }
        if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Archive-root links are forbidden.'
        }
        $expectedDirectory = $entry.Name -in @('snapshot', 'evidence')
        if ($expectedDirectory -ne ($entry -is [IO.DirectoryInfo])) {
            throw 'Archive-root entry has the wrong type.'
        }
        if ($entry.Name -ne 'snapshot') { $pending.Push($entry) }
    }
    while ($pending.Count -gt 0) {
        $entry = $pending.Pop()
        if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Evidence links are forbidden.'
        }
        Assert-PrivateAccess $entry
        if ($entry -is [IO.DirectoryInfo]) {
            foreach ($child in $entry.EnumerateFileSystemInfos()) { $pending.Push($child) }
        }
    }
}

function Assert-Archive($Root, $Receipt, $Expected, [string]$Original) {
    Assert-ArchiveSurface $Root
    $snapshot = Join-Path $Root 'snapshot'
    $null = Get-SafeRoot $snapshot
    $actual = Get-Inventory $snapshot -Private
    Assert-MatchingInventory $Expected $actual -Snapshot
    if ($Original) {
        $current = Get-Inventory $Original
        Assert-MatchingInventory $Expected $current
    }
    $bundle = Join-Path $Root 'history.bundle'
    if ((Get-Hash $bundle) -ne $Receipt.bundleSha256) { throw 'Git bundle hash mismatch.' }
    if ((Get-Hash (Join-Path $Root 'inventory.json')) -ne $Receipt.inventorySha256) {
        throw 'Inventory hash mismatch.'
    }
    $null = Invoke-Git $snapshot @('bundle', 'verify', $bundle)
    $state = Get-GitState $snapshot
    if ($state.head -ne $Receipt.git.head -or
        ($state.refs -join "`n") -ne ($Receipt.git.refs -join "`n")) {
        throw 'Recovered Git identity differs.'
    }
    # Links are metadata, so archived Git status may omit an untracked link.
    if ($Original) {
        $sourceState = Get-GitState $Original
        if (($sourceState | ConvertTo-Json -Compress) -ne ($Receipt.git | ConvertTo-Json -Compress)) {
            throw 'Original Git identity or working state changed.'
        }
    }
}

try {
    $ArchiveRoot = Get-SafeRoot $ArchiveRoot
    Assert-OutsideGit $ArchiveRoot
    if ($SourceRoot) {
        $SourceRoot = Get-SafeRoot $SourceRoot
        Assert-SeparateRoots $SourceRoot $ArchiveRoot
    }
    if ($Action -eq 'Capture') {
        if (-not $SourceRoot) { throw 'Capture requires SourceRoot.' }
        if (Test-Path -LiteralPath $ArchiveRoot) { throw 'Capture refuses an existing target.' }
        Assert-StandaloneGit $SourceRoot
        $gitState = Get-GitState $SourceRoot
        $null = [IO.Directory]::CreateDirectory($ArchiveRoot)
        Set-PrivateRoot $ArchiveRoot
        $evidence = Join-Path $ArchiveRoot 'evidence'
        $null = [IO.Directory]::CreateDirectory($evidence)
        [Console]::Error.WriteLine('Retirement: hashing source inventory.')
        $inventory = Get-Inventory $SourceRoot
        $inventoryPath = Join-Path $ArchiveRoot 'inventory.json'
        Write-Json $inventoryPath $inventory
        $snapshot = Join-Path $ArchiveRoot 'snapshot'
        $copyArguments = @($SourceRoot, $snapshot, '/E', '/XJ', '/XJD', '/XJF', '/SL',
            '/COPY:DAT', '/DCOPY:DAT', '/R:0', '/W:0', '/MT:8', '/NP', '/NFL', '/NDL',
            '/NJH', '/NJS', "/LOG:$(Join-Path $evidence 'robocopy.log')")
        $directoryLinks = @($inventory.links | Where-Object directory)
        $fileLinks = @($inventory.links | Where-Object { -not $_.directory })
        if ($directoryLinks.Count) {
            $copyArguments += '/XD'
            $copyArguments += @($directoryLinks | ForEach-Object { Join-Path $SourceRoot $_.path })
        }
        if ($fileLinks.Count) {
            $copyArguments += '/XF'
            $copyArguments += @($fileLinks | ForEach-Object { Join-Path $SourceRoot $_.path })
        }
        [Console]::Error.WriteLine("Retirement: copying $($inventory.fileCount) ordinary files.")
        & robocopy @copyArguments | Out-Null
        $copyExit = $LASTEXITCODE
        if ($copyExit -ge 8) { throw 'Robocopy reported an incomplete copy.' }
        $bundle = Join-Path $ArchiveRoot 'history.bundle'
        $null = Invoke-Git $SourceRoot @('bundle', 'create', $bundle, '--all')
        $receipt = [pscustomobject]@{
            schema = $schema; result = 'verified'; sourceRoot = $SourceRoot
            archiveRoot = $ArchiveRoot; capturedAtUtc = [DateTime]::UtcNow.ToString('o')
            ownerSid = $userSid.Value; git = $gitState; robocopyExit = $copyExit
            fileCount = $inventory.fileCount; totalBytes = $inventory.totalBytes
            linkCount = $inventory.links.Count; inventorySha256 = (Get-Hash $inventoryPath)
            bundleSha256 = (Get-Hash $bundle)
        }
        [Console]::Error.WriteLine('Retirement: verifying copy, permissions and unchanged source.')
        Assert-Archive $ArchiveRoot $receipt $inventory $SourceRoot
        Write-Json (Join-Path $ArchiveRoot 'capture.json') $receipt
    } else {
        Assert-ArchiveSurface $ArchiveRoot
        $receipt = Get-Content -LiteralPath (Join-Path $ArchiveRoot 'capture.json') -Raw | ConvertFrom-Json
        if ($receipt.schema -ne $schema -or $receipt.result -ne 'verified') {
            throw 'A completed capture receipt is required.'
        }
        $inventoryPath = Join-Path $ArchiveRoot 'inventory.json'
        if ((Get-Hash $inventoryPath) -ne $receipt.inventorySha256) {
            throw 'Inventory hash mismatch.'
        }
        $inventory = Get-Content -LiteralPath $inventoryPath -Raw | ConvertFrom-Json
        Assert-Archive $ArchiveRoot $receipt $inventory $SourceRoot
    }
    [pscustomobject]@{
        schema = $schema; result = 'verified'; archiveRoot = $ArchiveRoot
        fileCount = $receipt.fileCount; totalBytes = $receipt.totalBytes
        linkCount = $receipt.linkCount; inventorySha256 = $receipt.inventorySha256
        bundleSha256 = $receipt.bundleSha256
    } | ConvertTo-Json
} catch {
    [pscustomobject]@{
        schema = $schema; result = 'failed'; error = $_.Exception.Message
    } | ConvertTo-Json
    exit 1
}

from django.db import migrations, models
import django.db.models.deletion

import bug_metrics.models


def backfill_scope_provider_bindings(apps, schema_editor):
    scope_model = apps.get_model('bug_metrics', 'JiraScopeConfig')
    binding_model = apps.get_model('bug_metrics', 'BugTrendScopeProviderBinding')
    for scope in scope_model.objects.filter(enabled=True):
        profile_id = scope.name
        provider_id = ''
        status = 'configuration_required'
        provenance = {'source': 'migration'}
        blockers = []
        normalized_name = str(scope.name or '').lower()
        if normalized_name == 'chiplet-2a-jira':
            profile_id = 'chiplet-2a-jira'
            provider_id = 'jira'
            status = 'explicit'
            provenance = {'source': 'migration', 'matched_by': 'known_profile_id'}
        elif 'hsdes' in normalized_name:
            provider_id = 'hsdes'
            status = 'compatibility'
            provenance = {'source': 'migration', 'matched_by': 'legacy_scope_name'}
        elif scope.jql:
            provider_id = 'jira'
            status = 'compatibility'
            provenance = {'source': 'migration', 'matched_by': 'legacy_jira_scope'}
        else:
            blockers = [{
                'code': 'scope_binding_missing',
                'message': 'Scope is not bound to a provider profile.',
            }]
        binding_model.objects.update_or_create(
            scope_id=scope.id,
            defaults={
                'profile_id': profile_id if provider_id else '',
                'provider_id': provider_id,
                'status': status,
                'provenance': provenance,
                'blockers': blockers,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('bug_metrics', '0012_rehash_normalized_scope_semantics'),
    ]

    operations = [
        migrations.CreateModel(
            name='BugTrendScopeProviderBinding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('profile_id', models.CharField(blank=True, max_length=120)),
                ('provider_id', models.CharField(blank=True, max_length=80)),
                ('status', models.CharField(choices=[('explicit', 'Explicit'), ('compatibility', 'Compatibility'), ('configuration_required', 'Configuration required'), ('ambiguous', 'Ambiguous'), ('disabled', 'Disabled')], default='configuration_required', max_length=40)),
                ('provenance', models.JSONField(default=bug_metrics.models._empty_dict)),
                ('blockers', models.JSONField(default=bug_metrics.models._empty_list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('scope', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='provider_binding', to='bug_metrics.jirascopeconfig')),
            ],
        ),
        migrations.AddIndex(
            model_name='bugtrendscopeproviderbinding',
            index=models.Index(fields=['profile_id', 'provider_id', 'status'], name='bug_metrics_profile_2b3100_idx'),
        ),
        migrations.RunPython(backfill_scope_provider_bindings, migrations.RunPython.noop),
    ]

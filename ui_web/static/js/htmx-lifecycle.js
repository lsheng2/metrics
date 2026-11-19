/*
 * htmx request lifecycle: the progress bar while requests are in flight, error toasts for
 * failed or unreachable requests, and re-rendering the bug-trend chart partial after swaps.
 * Loads after the page modules so pane layout has sized the chart container first.
 */

document.addEventListener('DOMContentLoaded', function() {
    let activeRequestCount = 0;

    function showLoadingIndicator() {
        activeRequestCount += 1;
        const indicator = document.getElementById('loading-indicator');
        if (indicator) {
            indicator.classList.remove('is-hidden');
        }
    }

    function hideLoadingIndicator() {
        activeRequestCount = Math.max(0, activeRequestCount - 1);
        if (activeRequestCount > 0) {
            return;
        }
        const indicator = document.getElementById('loading-indicator');
        if (indicator) {
            indicator.classList.add('is-hidden');
        }
    }

    function appendParagraph(parent, text, strong) {
        const paragraph = document.createElement('p');
        if (strong) {
            const emphasis = document.createElement('strong');
            emphasis.textContent = text;
            paragraph.append(emphasis);
        } else {
            paragraph.textContent = text;
        }
        parent.append(paragraph);
    }

    // The toast is a danger message; #notification-container is the polite live region and
    // carries the translated copy in data-message-* attributes.
    function showErrorNotification(url, statusCode, statusText) {
        const container = document.getElementById('notification-container');
        if (!container) {
            return;
        }
        const messages = container.dataset;

        const header = document.createElement('div');
        header.className = 'message-header';
        appendParagraph(header, statusCode ? messages.messageRequestFailed : messages.messageNetworkError, false);
        const dismiss = document.createElement('button');
        dismiss.type = 'button';
        dismiss.className = 'delete';
        dismiss.setAttribute('aria-label', messages.messageDismiss);
        dismiss.addEventListener('click', function() {
            container.replaceChildren();
        });
        header.append(dismiss);

        const body = document.createElement('div');
        body.className = 'message-body';
        appendParagraph(body, statusCode ? `${statusCode} ${statusText}: ${url}` : url, true);
        if (statusCode === 503) {
            appendParagraph(body, messages.messageWafRetry, false);
        }

        const toast = document.createElement('div');
        toast.className = 'message is-danger';
        toast.append(header, body);
        container.replaceChildren(toast);
    }

    document.body.addEventListener('htmx:beforeRequest', showLoadingIndicator);
    document.body.addEventListener('htmx:afterRequest', hideLoadingIndicator);
    document.body.addEventListener('htmx:afterSwap', function() {
        if (typeof window.initBugTrendChart === 'function') {
            window.initBugTrendChart();
        }
    });

    document.body.addEventListener('htmx:responseError', function(event) {
        const url = event.detail.pathInfo.requestPath;
        const statusCode = event.detail.xhr.status;
        const statusText = event.detail.xhr.statusText;
        showErrorNotification(url, statusCode, statusText);
    });

    document.body.addEventListener('htmx:sendError', function(event) {
        const url = event.detail.pathInfo.requestPath;
        showErrorNotification(url, null, null);
    });
});

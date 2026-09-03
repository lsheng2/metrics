(function() {
    function requestHtml(url, options) {
        var method = options.method || 'GET';
        var headers = {'X-Requested-With': 'XMLHttpRequest'};
        var fetchOptions = {method: method, headers: headers};
        if (options.body) {
            fetchOptions.body = options.body;
        }
        document.body.dispatchEvent(new CustomEvent('htmx:beforeRequest', {
            detail: {pathInfo: {requestPath: url}}
        }));
        return fetch(url, fetchOptions).then(function(response) {
            return response.text().then(function(html) {
                return {response: response, html: html};
            });
        }).then(function(result) {
            if (!result.response.ok) {
                document.body.dispatchEvent(new CustomEvent('htmx:responseError', {
                    detail: {
                        pathInfo: {requestPath: url},
                        xhr: {status: result.response.status, statusText: result.response.statusText}
                    }
                }));
                return;
            }
            swapHtml(result.html, options);
            document.body.dispatchEvent(new CustomEvent('htmx:afterRequest', {
                detail: {pathInfo: {requestPath: url}}
            }));
            document.body.dispatchEvent(new CustomEvent('htmx:afterSwap', {
                detail: {pathInfo: {requestPath: url}}
            }));
        }).catch(function() {
            document.body.dispatchEvent(new CustomEvent('htmx:sendError', {
                detail: {pathInfo: {requestPath: url}}
            }));
        });
    }

    function swapHtml(html, options) {
        var target = document.querySelector(options.target);
        if (!target) {
            return;
        }
        var selected = null;
        if (options.select) {
            selected = new DOMParser().parseFromString(html, 'text/html').querySelector(options.select);
        }
        var content = selected ? selected.outerHTML : html;
        if (options.swap === 'outerHTML') {
            target.outerHTML = content;
        } else {
            target.innerHTML = selected ? selected.innerHTML : content;
        }
    }

    if (!window.htmx) {
        window.htmx = {};
    }

    if (!window.htmx.ajax) {
        window.htmx.ajax = function(method, url, options) {
            options = options || {};
            options.method = method || 'GET';
            return requestHtml(url, options);
        };
    }

    document.addEventListener('click', function(event) {
        var trigger = event.target.closest('[hx-get]');
        if (!trigger || trigger.tagName === 'FORM') {
            return;
        }
        event.preventDefault();
        var url = trigger.getAttribute('hx-get');
        window.htmx.ajax('GET', url, {
            target: trigger.getAttribute('hx-target') || 'body',
            select: trigger.getAttribute('hx-select') || '',
            swap: trigger.getAttribute('hx-swap') || 'innerHTML'
        });
        if (trigger.getAttribute('hx-push-url') === 'true') {
            window.history.pushState({}, '', trigger.getAttribute('href') || url);
        }
    });

    document.addEventListener('submit', function(event) {
        var form = event.target.closest('form[hx-get]');
        if (!form) {
            return;
        }
        event.preventDefault();
        var params = new URLSearchParams(new FormData(form));
        var baseUrl = form.getAttribute('hx-get');
        var url = baseUrl + (baseUrl.indexOf('?') >= 0 ? '&' : '?') + params.toString();
        window.htmx.ajax('GET', url, {
            target: form.getAttribute('hx-target') || 'body',
            select: form.getAttribute('hx-select') || '',
            swap: form.getAttribute('hx-swap') || 'innerHTML'
        });
        if (form.getAttribute('hx-push-url') === 'true') {
            window.history.pushState({}, '', url);
        }
    });

    if (window.Chart) {
        return;
    }

    window.Chart = function(context, config) {
        this.context = context;
        this.canvas = context.canvas;
        this.config = config;
        this.clickHandler = null;
        renderChart(this);
        attachChartClick(this);
    };

    window.Chart.prototype.destroy = function() {
        if (this.clickHandler) {
            this.canvas.removeEventListener('click', this.clickHandler);
        }
        this.context.clearRect(0, 0, this.canvas.width, this.canvas.height);
    };

    function renderChart(instance) {
        var context = instance.context;
        var canvas = instance.canvas;
        var data = instance.config.data || {};
        var labels = data.labels || [];
        var datasets = data.datasets || [];
        var width = canvas.width || canvas.clientWidth || 900;
        var height = canvas.height || canvas.clientHeight || 360;
        canvas.width = width;
        canvas.height = height;
        context.clearRect(0, 0, width, height);
        context.fillStyle = '#0f172a';
        context.fillRect(0, 0, width, height);
        context.strokeStyle = '#334155';
        context.lineWidth = 1;
        context.beginPath();
        context.moveTo(48, 20);
        context.lineTo(48, height - 44);
        context.lineTo(width - 20, height - 44);
        context.stroke();

        var maxValue = Math.max(1, maxDatasetValue(datasets));
        var groupWidth = (width - 90) / Math.max(1, labels.length);
        var barWidth = Math.max(2, Math.min(42, groupWidth / Math.max(1, datasets.length + 1)));
        datasets.forEach(function(dataset, datasetIndex) {
            var values = dataset.data || [];
            if (dataset.type === 'line') {
                drawLineDataset(context, dataset, values, groupWidth, maxValue, height);
                return;
            }
            context.fillStyle = fillColorFor(dataset);
            values.forEach(function(value, index) {
                var numericValue = Number(value) || 0;
                var barHeight = ((height - 80) * numericValue) / maxValue;
                var x = 58 + index * groupWidth + datasetIndex * barWidth;
                var y = height - 44 - barHeight;
                context.fillRect(x, y, barWidth - 2, barHeight);
            });
        });

        context.fillStyle = '#cbd5e1';
        context.font = '12px Segoe UI, Arial, sans-serif';
        labels.forEach(function(label, index) {
            if (index % Math.ceil(labels.length / 8 || 1) === 0) {
                context.fillText(String(label), 54 + index * groupWidth, height - 18);
            }
        });
    }

    function drawLineDataset(context, dataset, values, groupWidth, maxValue, height) {
        context.strokeStyle = dataset.borderColor || fillColorFor(dataset);
        context.fillStyle = dataset.borderColor || fillColorFor(dataset);
        context.lineWidth = 2;
        context.beginPath();
        values.forEach(function(value, index) {
            var numericValue = Number(value) || 0;
            var x = 58 + index * groupWidth + (groupWidth / 2);
            var y = height - 44 - (((height - 80) * numericValue) / maxValue);
            if (index === 0) {
                context.moveTo(x, y);
            } else {
                context.lineTo(x, y);
            }
        });
        context.stroke();
        values.forEach(function(value, index) {
            if (Number(value) <= 0) {
                return;
            }
            var x = 58 + index * groupWidth + (groupWidth / 2);
            var y = height - 44 - (((height - 80) * Number(value)) / maxValue);
            context.beginPath();
            context.arc(x, y, 3, 0, Math.PI * 2);
            context.fill();
        });
    }

    function attachChartClick(instance) {
        var options = instance.config.options || {};
        if (!options.onClick) {
            return;
        }
        instance.clickHandler = function(event) {
            var data = instance.config.data || {};
            var labels = data.labels || [];
            var datasets = data.datasets || [];
            var rect = instance.canvas.getBoundingClientRect();
            var x = (event.clientX - rect.left) * (instance.canvas.width / Math.max(1, rect.width));
            var groupWidth = (instance.canvas.width - 90) / Math.max(1, labels.length);
        var pointIndex = Math.max(0, Math.min(labels.length - 1, Math.floor((x - 58) / groupWidth)));
        var datasetIndex = clickedDatasetIndex(instance, datasets, pointIndex, x, groupWidth);
        options.onClick(event, [{index: pointIndex, datasetIndex: datasetIndex}]);
    };
    instance.canvas.addEventListener('click', instance.clickHandler);
}

function clickedDatasetIndex(instance, datasets, pointIndex, x, groupWidth) {
    var barWidth = Math.max(2, Math.min(42, groupWidth / Math.max(1, datasets.length + 1)));
    var groupStart = 58 + pointIndex * groupWidth;
    var relativeX = x - groupStart;
    var index = Math.floor(relativeX / barWidth);
    if (index >= 0 && index < datasets.length && Number((datasets[index].data || [])[pointIndex]) > 0) {
        return index;
    }
    var nearest = 0;
    var nearestDistance = Number.MAX_VALUE;
    for (var candidate = 0; candidate < datasets.length; candidate += 1) {
        if (Number((datasets[candidate].data || [])[pointIndex]) <= 0) {
            continue;
        }
        var center = groupStart + candidate * barWidth + (barWidth / 2);
        var distance = Math.abs(center - x);
        if (distance < nearestDistance) {
            nearest = candidate;
            nearestDistance = distance;
        }
    }
    return nearest;
}

    function maxDatasetValue(datasets) {
        return datasets.reduce(function(maxValue, dataset) {
            return Math.max(maxValue, (dataset.data || []).reduce(function(datasetMax, value) {
                return Math.max(datasetMax, Number(value) || 0);
            }, 0));
        }, 0);
    }

    function fillColorFor(dataset) {
        if (dataset.backgroundColor && dataset.backgroundColor !== 'transparent') {
            return dataset.backgroundColor;
        }
        return dataset.borderColor || '#38bdf8';
    }
})();

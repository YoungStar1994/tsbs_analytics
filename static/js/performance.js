// 性能优化相关的JavaScript代码

// 请求缓存
const requestCache = new Map();
const CACHE_TTL = 5 * 60 * 1000; // 5分钟缓存

// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 节流函数
function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    }
}

// 缓存请求结果
function getCachedRequest(url, options = {}) {
    const cacheKey = JSON.stringify({ url, options });
    const cached = requestCache.get(cacheKey);
    
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
        return Promise.resolve(cached.data);
    }
    
    return fetch(url, options)
        .then(response => response.json())
        .then(data => {
            requestCache.set(cacheKey, {
                data: data,
                timestamp: Date.now()
            });
            
            // 限制缓存大小
            if (requestCache.size > 50) {
                const firstKey = requestCache.keys().next().value;
                requestCache.delete(firstKey);
            }
            
            return data;
        });
}

// 批量处理DOM更新
class DOMBatcher {
    constructor() {
        this.updates = [];
        this.scheduled = false;
    }
    
    add(updateFn) {
        this.updates.push(updateFn);
        if (!this.scheduled) {
            this.scheduled = true;
            requestAnimationFrame(() => {
                this.flush();
            });
        }
    }
    
    flush() {
        this.updates.forEach(update => update());
        this.updates = [];
        this.scheduled = false;
    }
}

const domBatcher = new DOMBatcher();

// 优化的表格渲染
function renderTableOptimized(data, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    // 虚拟滚动实现（简化版）
    const VISIBLE_ROWS = 50;
    const displayData = data.slice(0, VISIBLE_ROWS);
    
    domBatcher.add(() => {
        container.innerHTML = generateTableHTML(displayData);
        
        // 如果数据量大，显示分页信息
        if (data.length > VISIBLE_ROWS) {
            const info = document.createElement('div');
            info.className = 'pagination-info';
            info.textContent = `显示前 ${VISIBLE_ROWS} 条，共 ${data.length} 条记录`;
            container.appendChild(info);
        }
    });
}

// 生成表格HTML
function generateTableHTML(data) {
    if (!data || data.length === 0) {
        return '<div class="no-data">暂无数据</div>';
    }
    
    const headers = Object.keys(data[0]);
    const headerRow = headers.map(h => `<th>${h}</th>`).join('');
    
    const rows = data.map(row => {
        const cells = headers.map(header => {
            const value = row[header];
            return `<td>${value !== null && value !== undefined ? value : ''}</td>`;
        }).join('');
        return `<tr>${cells}</tr>`;
    }).join('');
    
    return `
        <table class="data-table">
            <thead><tr>${headerRow}</tr></thead>
            <tbody>${rows}</tbody>
        </table>
    `;
}

// 优化的图表更新
function updateChartOptimized(chartData, chartId) {
    if (!window.chartInstances) {
        window.chartInstances = {};
    }
    
    domBatcher.add(() => {
        const chartContainer = document.getElementById(chartId);
        if (!chartContainer) return;
        
        // 销毁旧图表
        if (window.chartInstances[chartId]) {
            window.chartInstances[chartId].dispose();
        }
        
        // 创建新图表
        const chart = echarts.init(chartContainer);
        const option = {
            title: { text: '性能趋势图' },
            tooltip: { trigger: 'axis' },
            legend: { data: Object.keys(chartData) },
            xAxis: { type: 'time' },
            yAxis: { type: 'value' },
            series: Object.values(chartData)
        };
        
        chart.setOption(option);
        window.chartInstances[chartId] = chart;
    });
}

// 性能监控
class PerformanceMonitor {
    constructor() {
        this.metrics = {};
    }
    
    start(name) {
        this.metrics[name] = { start: performance.now() };
    }
    
    end(name) {
        if (this.metrics[name]) {
            this.metrics[name].duration = performance.now() - this.metrics[name].start;
            console.log(`${name}: ${this.metrics[name].duration.toFixed(2)}ms`);
        }
    }
    
    getMetrics() {
        return Object.keys(this.metrics).map(name => ({
            name,
            duration: this.metrics[name].duration
        }));
    }
}

const perfMonitor = new PerformanceMonitor();

// 导出函数供全局使用
window.performanceUtils = {
    debounce,
    throttle,
    getCachedRequest,
    renderTableOptimized,
    updateChartOptimized,
    perfMonitor,
    domBatcher
};

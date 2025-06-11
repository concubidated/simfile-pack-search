let chartInstance = null;


function updateChartGraph(data) {
    const ctx = document.getElementById("chart-density").getContext("2d");
    const maxTimeInSeconds = 150;  // 2 min 30 sec

    if (window.chartInstance) {
        window.chartInstance.destroy();
    }

    if (chartInstance) {
        chartInstance.destroy();
    }

    // Create gradient fill
    const gradient = ctx.createLinearGradient(0, 0, 0, 200);
    gradient.addColorStop(0, 'rgba(0, 123, 255, 0.6)');  // top
    gradient.addColorStop(1, 'rgba(0, 123, 255, 0.1)');  // bottom

    chartInstance = new Chart(ctx, {
    type: 'line',
    data: {
        //labels: data.map((_, i) => i),
        labels: data.map((_, index) => index),
        datasets: [{
            label: '',
            data: data,
            fill: true,
            backgroundColor: gradient,
            borderWidth: 1,
            borderColor: 'rgba(0, 123, 255, 0.9)',
            tension: 0.4,
            pointRadius: 0
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
        x: {
            type: 'linear',

            ticks: {
                color: '#ccc',
                font: { size: 12 },
                display: false,
                //callback: function(value) {
                //    const minutes = Math.floor(value / 60);
                //    const seconds = Math.floor(value % 60).toString().padStart(2, '0');
                //    return `${minutes}:${seconds}`;
                //},
            },
            grid: { display: false },
        },
        y: {
            grid: { display: false },
            beginAtZero: true,
            ticks: {
            color: '#ccc',
            font: { size: 12 },
            stepSize: 3
            }
        }
        },
        plugins: {
        legend: { display: false },
        tooltip: {
            backgroundColor: '#222',
            titleColor: '#fff',
            bodyColor: '#fff'
        }
        }
    }
    });


}

function checkHashOnLoad() {
    const fragment = window.location.hash.replace('#', ''); // remove the `#`
    if (fragment) {
        loadChart(fragment); // call your function with the ID
        const $button = $(`#button-${fragment}`);
        if ($button.length) {
            $button.prop('checked', true);
        }
        return true;
    }
    return false;
}

function drawNoteField(chart, zoom) {
    if (chart.notes[0][1][0].length < 6) {
        size = 64;
    } else {
        size = 32;
    }
    
    var length = ((chart.notes.length * size * zoom) + size)
	$(`#fake-scroll`).height(length)
	var scrollTop = $(`#scrollbar-notes`).scrollTop();

    const startMeasure = Math.floor(scrollTop / (size * zoom));
    const endMeasure = Math.min(startMeasure + 24, chart.notes.length - 1);

    let visibleNotes = chart.notes.slice(startMeasure, endMeasure + 1);
    if (visibleNotes.length === 0 && startMeasure < chart.notes.length) {
        visibleNotes = [chart.notes[startMeasure]];
    }

    // pixel offset
    const pixelOffset = scrollTop % (size * zoom);
    render(canvas, visibleNotes, zoom, chart.charttype);
    canvas.css({
        'transform': `translateY(-${pixelOffset}px)`,
        'transform-origin': 'top-left'
    });
}

/**
function setTheme (mode = 'auto') {
    const userMode = localStorage.getItem('bs-theme');
    const sysMode = window.matchMedia('(prefers-color-scheme: light)').matches;
    const useSystem = mode === 'system' || (!userMode && mode === 'auto');
    const modeChosen = useSystem ? 'system' : mode === 'dark' || mode === 'light' ? mode : userMode;
  
    if (useSystem) {
      localStorage.removeItem('bs-theme');
    } else {
      localStorage.setItem('bs-theme', modeChosen);
    }
  
    document.documentElement.setAttribute('data-bs-theme', useSystem ? (sysMode ? 'light' : 'dark') : modeChosen);
    //document.querySelectorAll('.mode-switch .btn').forEach(e => e.classList.remove('text-body'));
    //document.getElementById(modeChosen).classList.add('text-body');
  }
  
  setTheme();
  document.querySelectorAll('.mode-switch .btn').forEach(e => e.addEventListener('click', () => setTheme(e.id)));
  window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', () => setTheme());
**/

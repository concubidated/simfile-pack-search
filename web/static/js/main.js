function createDensityChart(ctx, data) {
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map((_, index) => index),
            datasets: [{
                data: data,
                borderColor: 'blue',
                borderWidth: 0,
		backgroundColor: 'grey',
                fill: true,
                tension: 0.4 // Interpolation mode for smooth curves
            }]
        },
        options: {
            elements: {
                    point: {
                            radius: 0,
                    }
            },
            responsive: false,
            maintainAspectRatio: false,
            scales: {
                x: {
                    display: false // Hides x-axis since labels aren't needed
                },
                y: {
                    display: true, // Hides y-axis for simplicity
                    //suggestedMax: 15,
                }
            },
            plugins: {
                legend: {
                    display: false // No legend for a minimal look
                }
            }
        }
    });
}

function checkHashOnLoad() {
    const fragment = window.location.hash.replace('#', ''); // remove the `#`
    if (fragment) {
        hideOthers(fragment); // call your function with the ID
        const $button = $(`#button-${fragment}`);
        if ($button.length) {
            $button.prop('checked', true);
        }
    }
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

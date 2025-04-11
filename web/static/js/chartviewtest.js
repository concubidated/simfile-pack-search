const rotates = {
	'dance-single': [90, 0, 180, 270],
	'dance-double': [90, 0, 180, 270, 90, 0, 180, 270],
	'dance-solo': [90, 135, 0, 180, 225, 270],
	'smx-single': [90, 0, 0, 180, 270],
	'smx-double10': [90, 0, 0, 180, 270, 90, 0, 0, 180, 270],
	'pump-single': [45, 135, 0, 225, 315],
	'pump-double': [45, 135, 0, 225, 315, 45, 135, 0, 225, 315]
}
var size = 64, zoom = 10;
function render($canvas, notes, zoom=8, style='dance-single') {
    style = rotates[style] ? style : "dance-single";
    var columnCount = rotates[style].length;
    const holds = new Array(columnCount).fill(false);
    var startMeasure = notes[0][0];
    var end = notes[notes.length - 1][0] + 1;
    var margin = ($canvas.width() - (columnCount * size)) / 2;
    $canvas.clearCanvas().prop("height", Math.min(32767, ((end - startMeasure) * size * zoom) + size));
    for (var i = startMeasure; i <= end; i++) {
        $canvas.drawLine({
            strokeStyle: "#333",
            strokeWidth: 2,
            x1: 0,
            y1: ((i - startMeasure) * size * zoom) + (size / 2),
            x2: 640,
            y2: ((i - startMeasure) * size * zoom) + (size / 2)
        }).drawLine({
            strokeStyle: "#999",
            strokeWidth: 2,
            x1: 0,
            y1: ((i - startMeasure - 0.5) * size * zoom) + (size / 2),
            x2: 640,
            y2: ((i - startMeasure - 0.5) * size * zoom) + (size / 2)
        }).drawLine({
            strokeStyle: "#ccc",
            strokeWidth: 2,
            x1: 0,
            y1: ((i - startMeasure - 0.25) * size * zoom) + (size / 2),
            x2: 640,
            y2: ((i - startMeasure - 0.25) * size * zoom) + (size / 2)
        }).drawLine({
            strokeStyle: "#ccc",
            strokeWidth: 2,
            x1: 0,
            y1: ((i - startMeasure - 0.75) * size * zoom) + (size / 2),
            x2: 640,
            y2: ((i - startMeasure - 0.75) * size * zoom) + (size / 2)
        });
    }
    for (var i in notes) {
        var bar = notes[i][0];
        var dirs = notes[i][1];
        for (var j = 0; j < dirs.length; j++) {
            for (var k in dirs[j]) {
                var step = dirs[j][k];
                switch (step) {
                    case "M": // Mine
                        $canvas.drawImage({
                            source: "/static/images/chartview/mine.png",
                            x: (k * size) + margin,
                            y: ((bar - startMeasure) + (j / dirs.length)) * size * zoom,
                            width: size,
                            height: size,
                            fromCenter: false,
                            sx: 0,
                            sy: 0,
                            sWidth: 128,
                            sHeight: 128,
                            cropFromCenter: false,
                        });
                    break;
                    case "1": // step
			var imagePath = "/static/images/chartview/notes.png"
                        if (style.includes("smx") || style.includes("pump")) {
			    if (k == 2 || k == 7){
                                imagePath = "/static/images/chartview/center.png";
			    }
			}
                        $canvas.drawImage({
                            source: imagePath,
                            x: (k * size) + margin,
                            y: ((bar - startMeasure) + (j / dirs.length)) * size * zoom,
                            width: size,
                            height: size,
                            fromCenter: false,
                            sx: 0,
                            sy: (noteColor(j, dirs.length) + 0.5) * 128,
                            sWidth: 128,
                            sHeight: 128,
                            cropFromCenter: false,
                            rotate: rotates[style][k]
                        });
                        break;
                    case "2": // hold start
                    case "4": // roll start
                        holds[k] = [bar, j, dirs.length];
                        break;
                    case "3": // hold/roll stop
			var notesImg = "/static/images/chartview/notes.png";
			var holdImg = "/static/images/chartview/hold.png";
			var holdEndImg = "/static/images/chartview/hold-end.png";
                        if (style.includes("smx") || style.includes("pump")) {
			    if (k == 2 || k == 7){
				notesImg = "/static/images/chartview/center.png";
                                holdImg = "/static/images/chartview/center-hold.png";
				holdEndImg = "/static/images/chartview/center-hold-end.png";
			    }
			}
                        var hBar = holds[k][0];
                        var hJ = holds[k][1];
                        var hDirsLength = holds[k][2];
                        var hPos = hBar + (hJ / hDirsLength);
                        $canvas.drawImage({
                            source: holdImg,
                            x: (k * size) + margin,
                            y: ((hBar - startMeasure) + (hJ / hDirsLength))  * size * zoom + (size / 2),
                            width: size,
                            height: ((bar - hBar) + ((j / dirs.length) - (hJ / hDirsLength))) * size * zoom,
                            fromCenter: false
                        }).drawImage({
                            source: holdEndImg,
                            x: (k * size) + margin,
                            y: ((bar - startMeasure) + (j / dirs.length)) * size * zoom + (size / 2),
                            width: size,
                            height: size / 2,
                            fromCenter: false
                        }).drawImage({
                            source: notesImg,
                            x: (k * size) + margin,
                            y: ((hBar - startMeasure) + (hJ / hDirsLength)) * size * zoom,
                            width: size,
                            height: size,
                            fromCenter: false,
                            sx: 0,
                            sy: (noteColor(hJ, hDirsLength) + 0.5) * 128,
                            sWidth: 128,
                            sHeight: 128,
                            cropFromCenter: false,
                            rotate: rotates[style][k]
                        });
                        holds[k] = false;
                        break;
                }
            }
        }
    }
}

var imgs = ["notes", "hold", "hold-end"];
for (var i in imgs) (new Image()).src = "/static/images/chartview/" + imgs[i] + ".png";

function noteColor(beat, size) {
    var divs = 3 * 128;
    var val = beat * divs / size;
    if (val % (divs / 4) === 0) {
        return 0;
    } else if (val % (divs / 8) === 0) {
        return 1;
    } else if (val % (divs / 12) === 0) {
        return 2;
    } else if (val % (divs / 16) === 0) {
        return 3;
    } else if (val % (divs / 24) === 0) {
        return 4;
    } else if (val % (divs / 32) === 0) {
        return 5;
    } else if (val % (divs / 64) === 0) {
        return 6;
    } else {
        return 7;
    }
};

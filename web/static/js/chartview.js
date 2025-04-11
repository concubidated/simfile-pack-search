var arrows = ["<", "V", "\u039b", ">"];
var rotates = [90, 0, 180, 270];
var size = 64, zoom = 10;
function render($canvas, notes, zoom=8) {
    const holds = new Array(notes[0][1][0].length).fill(false);
    var end = notes[notes.length - 1][0] + 1;
    var margin = ($canvas.width() - (4 * size)) / 2;
    $canvas.clearCanvas().prop("height", Math.min(32767, (end * size * zoom) + size));
    for (var i = 0; i <= end; i++) {
        $canvas.drawLine({
            strokeStyle: "#333",
            strokeWidth: 2,
            x1: 0,
            y1: (i * size * zoom) + (size / 2),
            x2: 512,
            y2: (i * size * zoom) + (size / 2)
        }).drawLine({
            strokeStyle: "#999",
            strokeWidth: 2,
            x1: 0,
            y1: ((i - 0.5) * size * zoom) + (size / 2),
            x2: 512,
            y2: ((i - 0.5) * size * zoom) + (size / 2)
        }).drawLine({
            strokeStyle: "#ccc",
            strokeWidth: 2,
            x1: 0,
            y1: ((i - 0.25) * size * zoom) + (size / 2),
            x2: 512,
            y2: ((i - 0.25) * size * zoom) + (size / 2)
        }).drawLine({
            strokeStyle: "#ccc",
            strokeWidth: 2,
            x1: 0,
            y1: ((i - 0.75) * size * zoom) + (size / 2),
            x2: 512,
            y2: ((i - 0.75) * size * zoom) + (size / 2)
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
                            y: (bar + (j / dirs.length)) * size * zoom,
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
                        $canvas.drawImage({
                            source: "/static/images/chartview/notes.png",
                            x: (k * size) + margin,
                            y: (bar + (j / dirs.length)) * size * zoom,
                            width: size,
                            height: size,
                            fromCenter: false,
                            sx: 0,
                            sy: (noteColor(j, dirs.length) + 0.5) * 128,
                            sWidth: 128,
                            sHeight: 128,
                            cropFromCenter: false,
                            rotate: rotates[k]
                        });
                        break;
                    case "2": // hold start
                    case "4": // roll start
                        holds[k] = [bar, j, dirs.length];
                        break;
                    case "3": // hold/roll stop
                        var hBar = holds[k][0];
                        var hJ = holds[k][1];
                        var hDirsLength = holds[k][2];
                        var hPos = hBar + (hJ / hDirsLength);
                        $canvas.drawImage({
                            source: "/static/images/chartview/hold.png",
                            x: (k * size) + margin,
                            y: (hPos * size * zoom) + (size / 2),
                            width: size,
                            height: (bar + (j / dirs.length) - hPos) * size * zoom,
                            fromCenter: false
                        }).drawImage({
                            source: "/static/images/chartview/hold-end.png",
                            x: (k * size) + margin,
                            y: ((bar + (j / dirs.length)) * size * zoom) + (size / 2),
                            width: size,
                            height: size / 2,
                            fromCenter: false
                        }).drawImage({
                            source: "/static/images/chartview/notes.png",
                            x: (k * size) + margin,
                            y: hPos * size * zoom,
                            width: size,
                            height: size,
                            fromCenter: false,
                            sx: 0,
                            sy: (noteColor(hJ, hDirsLength) + 0.5) * 128,
                            sWidth: 128,
                            sHeight: 128,
                            cropFromCenter: false,
                            rotate: rotates[k]
                        });
                        holds[k] = false;
                        break;
                    default:
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
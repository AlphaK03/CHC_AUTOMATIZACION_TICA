import QtQuick

Canvas {
    id: icon
    property string name: "grid"
    property color tint: Theme.muted
    implicitWidth: 22
    implicitHeight: 22
    onNameChanged: requestPaint()
    onTintChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
        let c = getContext("2d")
        c.reset()
        c.scale(width / 24, height / 24)
        c.strokeStyle = tint
        c.fillStyle = tint
        c.lineWidth = 1.6
        c.lineCap = "round"
        c.lineJoin = "round"
        function line(x1,y1,x2,y2) { c.moveTo(x1,y1); c.lineTo(x2,y2) }
        function circle(x,y,r) { c.moveTo(x+r,y); c.arc(x,y,r,0,Math.PI*2) }
        c.beginPath()
        if (name === "user") {
            circle(12,8,4); c.moveTo(4,22); c.bezierCurveTo(4,12,20,12,20,22)
        } else if (name === "grid") {
            c.rect(4,4,6,6); c.rect(14,4,6,6); c.rect(4,14,6,6); c.rect(14,14,6,6)
        } else if (name === "ship") {
            line(7,11,7,5); line(7,5,17,5); line(17,5,17,11); line(12,5,12,2)
            c.moveTo(3,12); c.lineTo(12,9); c.lineTo(21,12); c.lineTo(18,18); c.lineTo(6,18); c.closePath()
            c.moveTo(3,21); c.quadraticCurveTo(6,18,9,21); c.quadraticCurveTo(12,18,15,21); c.quadraticCurveTo(18,18,21,21)
        } else if (name === "document" || name === "receipt") {
            c.moveTo(6,3); c.lineTo(15,3); c.lineTo(19,7); c.lineTo(19,21); c.lineTo(5,21); c.lineTo(5,3); c.closePath()
            line(14,3,14,8); line(14,8,19,8); line(8,12,16,12); line(8,16,14,16)
            if (name === "receipt") { line(8,19,10,19); line(13,19,16,19) }
        } else if (name === "route") {
            circle(5,5,2); circle(19,19,2)
            c.moveTo(8,5); c.lineTo(16,5); c.bezierCurveTo(23,5,23,12,16,12); c.lineTo(8,12); c.bezierCurveTo(1,12,1,19,8,19); c.lineTo(15,19)
        } else if (name === "activity") {
            c.moveTo(2,13); c.lineTo(7,13); c.lineTo(10,5); c.lineTo(14,20); c.lineTo(17,10); c.lineTo(22,10)
        } else if (name === "arrow") { line(5,12,19,12); line(14,7,19,12); line(19,12,14,17)
        } else if (name === "chevron") { line(9,6,15,12); line(15,12,9,18)
        } else if (name === "collapse") { c.rect(3,4,18,16); line(9,4,9,20); line(16,9,13,12); line(13,12,16,15)
        } else if (name === "expand") { c.rect(3,4,18,16); line(9,4,9,20); line(13,9,16,12); line(16,12,13,15)
        } else if (name === "search") { circle(10,10,6); line(15,15,21,21)
        } else if (name === "plus") { line(12,5,12,19); line(5,12,19,12)
        } else if (name === "play") { c.moveTo(8,5); c.lineTo(19,12); c.lineTo(8,19); c.closePath()
        } else if (name === "pause") { line(8,5,8,19); line(16,5,16,19)
        } else if (name === "reset") { c.arc(12,12,8,-Math.PI/2,Math.PI*1.2); line(4,4,4,9); line(4,9,9,9)
        } else if (name === "check") { line(5,12,10,17); line(10,17,20,7)
        } else if (name === "download") { line(12,3,12,15); line(7,10,12,15); line(12,15,17,10); c.moveTo(4,16); c.lineTo(4,21); c.lineTo(20,21); c.lineTo(20,16)
        } else if (name === "database") { c.moveTo(4,5); c.bezierCurveTo(4,1,20,1,20,5); c.bezierCurveTo(20,9,4,9,4,5); line(4,5,4,19); line(20,5,20,19); c.moveTo(4,12); c.bezierCurveTo(4,16,20,16,20,12); c.moveTo(4,19); c.bezierCurveTo(4,23,20,23,20,19)
        } else if (name === "clock") { circle(12,12,9); line(12,6,12,12); line(12,12,16,14)
        } else if (name === "info") { circle(12,12,9); line(12,11,12,17); circle(12,7,0.5)
        } else if (name === "moon") { c.moveTo(19,16); c.bezierCurveTo(5,21,2,6,12,3); c.bezierCurveTo(7,12,14,17,19,16); c.closePath()
        } else if (name === "sun") { circle(12,12,4); for(let i=0;i<8;i++){let a=i*Math.PI/4; line(12+7*Math.cos(a),12+7*Math.sin(a),12+10*Math.cos(a),12+10*Math.sin(a))}
        } else if (name === "settings") { circle(12,12,4); circle(12,12,8); for(let i=0;i<8;i++){let a=i*Math.PI/4; line(12+8*Math.cos(a),12+8*Math.sin(a),12+10*Math.cos(a),12+10*Math.sin(a))}
        } else if (name === "close") { line(6,6,18,18); line(6,18,18,6)
        } else if (name === "folder") { c.moveTo(3,6); c.lineTo(10,6); c.lineTo(12,9); c.lineTo(21,9); c.lineTo(21,20); c.lineTo(3,20); c.closePath()
        } else if (name === "shield") { c.moveTo(12,2); c.lineTo(21,6); c.lineTo(20,14); c.quadraticCurveTo(18,20,12,23); c.quadraticCurveTo(6,20,4,14); c.lineTo(3,6); c.closePath(); line(8,12,11,15); line(11,15,16,9)
        } else if (name === "spark") { c.moveTo(12,2); c.lineTo(15,9); c.lineTo(22,12); c.lineTo(15,15); c.lineTo(12,22); c.lineTo(9,15); c.lineTo(2,12); c.lineTo(9,9); c.closePath() }
        c.stroke()
    }
}

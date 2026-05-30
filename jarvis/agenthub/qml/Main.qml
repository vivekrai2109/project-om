import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
    id: window
    property bool shellExpanded: !bridge.startMinimized
    property bool shellMaximized: false
    property bool settingsVisible: false
    property real collapsedX: 0
    property real collapsedY: 0
    property real dragPressX: 0
    property real dragPressY: 0
    property real dragWindowX: 0
    property real dragWindowY: 0
    property bool dragMoved: false
    readonly property int collapsedSize: 92
    readonly property int expandedWidth: 1420
    readonly property int expandedHeight: 880
    readonly property int terminalWidth: 360
    readonly property color accent: stateColor(bridge.assistantState)
    readonly property color secondaryAccent: bridge.assistantState === "listening" ? "#32ffc7" : bridge.assistantState === "speaking" ? "#8fbcff" : "#1da9ff"
    readonly property color tertiaryAccent: bridge.assistantState === "approval_required" ? "#ffc061" : "#9f7dff"
    readonly property color glass: "#0b1422"
    readonly property color glassAlt: "#0e1a2b"
    readonly property color edge: "#1c3550"
    readonly property color text: "#edf7ff"
    readonly property color muted: "#7ea8c9"
    readonly property var pendingApprovalModel: JSON.parse(bridge.pendingApprovalsJson)
    readonly property var workflowTraceModel: JSON.parse(bridge.workflowTraceJson)
    readonly property var visualOutputModel: JSON.parse(bridge.visualOutputJson)

    width: shellExpanded ? (shellMaximized ? Math.max(1100, Screen.width - 24) : expandedWidth) : collapsedSize
    height: shellExpanded ? (shellMaximized ? Math.max(720, Screen.height - 24) : expandedHeight) : collapsedSize
    minimumWidth: width
    minimumHeight: height
    maximumWidth: width
    maximumHeight: height
    visible: true
    color: "transparent"
    title: "Jarvis"
    flags: Qt.FramelessWindowHint | Qt.Window

    function stateColor(state) {
        if (state === "listening")
            return "#37f7d1"
        if (state === "thinking")
            return "#5bc0ff"
        if (state === "speaking")
            return "#8cbeff"
        if (state === "executing")
            return "#a875ff"
        if (state === "muted")
            return "#8897aa"
        if (state === "error")
            return "#ff6f91"
        if (state === "approval_required")
            return "#ffc061"
        return "#52f2ff"
    }

    function signalHeight(index) {
        let base = 26 + ((index % 5) * 10)
        if (bridge.assistantState === "idle")
            return base
        if (bridge.assistantState === "listening")
            return 44 + ((index % 2) * 32)
        if (bridge.assistantState === "thinking")
            return 28 + ((waveTicker.tick + index * 7) % 72)
        if (bridge.assistantState === "speaking")
            return 38 + ((waveTicker.tick * (index + 3)) % 98)
        if (bridge.assistantState === "executing")
            return 34 + ((waveTicker.tick + index * 17) % 54)
        if (bridge.assistantState === "muted")
            return 18 + ((index % 2) * 6)
        if (bridge.assistantState === "error")
            return index % 2 === 0 ? 100 : 16
        if (bridge.assistantState === "approval_required")
            return index % 3 === 0 ? 90 : 24
        return base
    }

    function statusGlowOpacity() {
        if (bridge.assistantState === "speaking")
            return 0.72
        if (bridge.assistantState === "listening")
            return 0.62
        if (bridge.assistantState === "thinking")
            return 0.54
        if (bridge.assistantState === "executing")
            return 0.64
        if (bridge.assistantState === "muted")
            return 0.22
        if (bridge.assistantState === "error")
            return 0.48
        return 0.34
    }

    function collapseShell() {
        shellExpanded = false
        shellMaximized = false
        settingsVisible = false
        window.x = collapsedX
        window.y = collapsedY
    }

    function expandShell() {
        shellExpanded = true
        settingsVisible = false
        shellMaximized = false
        window.x = Math.max(18, (Screen.width - width) / 2)
        window.y = Math.max(18, (Screen.height - height) / 2)
    }

    function toggleMaximizeShell() {
        if (!shellExpanded)
            shellExpanded = true
        shellMaximized = !shellMaximized
        settingsVisible = false
        if (shellMaximized) {
            window.x = 12
            window.y = 12
        } else {
            window.x = Math.max(18, (Screen.width - width) / 2)
            window.y = Math.max(18, (Screen.height - height) / 2)
        }
    }

    function moveShell(position) {
        if (!shellExpanded)
            shellExpanded = true
        if (position === "center") {
            window.x = Math.max(18, (Screen.width - width) / 2)
            window.y = Math.max(18, (Screen.height - height) / 2)
            return
        }
        if (position === "top-left") {
            window.x = 18
            window.y = 18
            return
        }
        if (position === "top-right") {
            window.x = Math.max(18, Screen.width - width - 18)
            window.y = 18
            return
        }
        if (position === "bottom-left") {
            window.x = 18
            window.y = Math.max(18, Screen.height - height - 48)
            return
        }
        if (position === "bottom-right") {
            window.x = Math.max(18, Screen.width - width - 18)
            window.y = Math.max(18, Screen.height - height - 48)
        }
    }

    function beginWindowDrag(mouseX, mouseY) {
        dragPressX = mouseX
        dragPressY = mouseY
        dragWindowX = window.x
        dragWindowY = window.y
        dragMoved = false
    }

    function dragWindow(mouseX, mouseY) {
        const dx = mouseX - dragPressX
        const dy = mouseY - dragPressY
        if (Math.abs(dx) > 4 || Math.abs(dy) > 4)
            dragMoved = true
        window.x = dragWindowX + dx
        window.y = dragWindowY + dy
        if (!shellExpanded) {
            collapsedX = window.x
            collapsedY = window.y
        }
    }

    Component.onCompleted: {
        collapsedX = Math.max(16, Screen.width - collapsedSize - 28)
        collapsedY = Math.max(16, Screen.height - collapsedSize - 56)
        if (shellExpanded)
            expandShell()
        else {
            window.x = collapsedX
            window.y = collapsedY
        }
    }

    Timer {
        id: waveTicker
        interval: 90
        running: true
        repeat: true
        property int tick: 0
        onTriggered: tick = (tick + 1) % 1000
    }

    Connections {
        target: bridge

        function onPendingApprovalsJsonChanged() {
            if (JSON.parse(bridge.pendingApprovalsJson).length > 0)
                expandShell()
        }

        function onStartMinimizedChanged() {
            if (!bridge.startMinimized)
                expandShell()
        }

        function onWindowCommandRequested(command) {
            if (command === "maximize") {
                if (!shellMaximized)
                    toggleMaximizeShell()
                return
            }
            if (command === "restore") {
                if (shellMaximized)
                    toggleMaximizeShell()
                else
                    expandShell()
                return
            }
            if (command === "minimize") {
                collapseShell()
                return
            }
            if (command === "move:center") {
                moveShell("center")
                return
            }
            if (command === "move:top-left") {
                moveShell("top-left")
                return
            }
            if (command === "move:top-right") {
                moveShell("top-right")
                return
            }
            if (command === "move:bottom-left") {
                moveShell("bottom-left")
                return
            }
            if (command === "move:bottom-right")
                moveShell("bottom-right")
        }
    }

    Rectangle {
        anchors.fill: parent
        radius: shellExpanded ? 34 : width / 2
        color: shellExpanded ? Qt.rgba(8 / 255, 13 / 255, 24 / 255, 0.96) : Qt.rgba(6 / 255, 12 / 255, 22 / 255, 0.92)
        border.color: Qt.rgba(accent.r, accent.g, accent.b, shellExpanded ? 0.28 : 0.52)
        border.width: 1

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            gradient: Gradient {
                GradientStop { position: 0.0; color: shellExpanded ? "#081422" : "#08131f" }
                GradientStop { position: 0.45; color: shellExpanded ? "#07111d" : "#06101a" }
                GradientStop { position: 1.0; color: "#02050b" }
            }
        }

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: "transparent"
            border.color: Qt.rgba(158 / 255, 217 / 255, 255 / 255, 0.06)
            border.width: 1
            anchors.margins: shellExpanded ? 8 : 3
        }
    }

    Item {
        anchors.fill: parent

        Item {
            visible: !shellExpanded
            anchors.fill: parent

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.OpenHandCursor
                onPressed: beginWindowDrag(mouseX, mouseY)
                onPositionChanged: dragWindow(mouseX, mouseY)
                onReleased: {
                    if (!dragMoved)
                        expandShell()
                }
            }

            Rectangle {
                anchors.centerIn: parent
                width: 62
                height: 62
                radius: 31
                color: "transparent"
                border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.36 + statusGlowOpacity() * 0.18)
                border.width: 2
                scale: 0.94 + statusGlowOpacity() * 0.16
                Behavior on scale { NumberAnimation { duration: 220; easing.type: Easing.InOutQuad } }
            }

            Rectangle {
                anchors.centerIn: parent
                width: 38
                height: 38
                radius: 19
                gradient: Gradient {
                    GradientStop { position: 0.0; color: secondaryAccent }
                    GradientStop { position: 1.0; color: "#072031" }
                }
                border.color: accent
                border.width: 2
            }

            Text {
                anchors.centerIn: parent
                text: "J"
                color: text
                font.pixelSize: 22
                font.bold: true
            }

            Rectangle {
                visible: bridge.listenStatus === "AUTO LISTEN // ON"
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 8
                width: 56
                height: 16
                radius: 8
                color: Qt.rgba(55 / 255, 247 / 255, 209 / 255, 0.18)
                border.color: Qt.rgba(55 / 255, 247 / 255, 209 / 255, 0.44)
                border.width: 1

                Text {
                    anchors.centerIn: parent
                    text: "LIVE"
                    color: "#37f7d1"
                    font.pixelSize: 8
                    font.bold: true
                    font.family: "Consolas"
                }
            }
        }

        Item {
            visible: shellExpanded
            anchors.fill: parent

            Rectangle {
                anchors.fill: parent
                radius: 34
                color: "transparent"

                Rectangle {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: dock.top
                    anchors.right: rightPanel.left
                    anchors.margins: 22
                    anchors.rightMargin: 12
                    radius: 30
                    color: Qt.rgba(10 / 255, 18 / 255, 31 / 255, 0.56)
                    border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.12)
                    border.width: 1

                    Rectangle {
                        anchors.fill: parent
                        radius: parent.radius
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: "#0b1727" }
                            GradientStop { position: 1.0; color: "#09111d" }
                        }
                        opacity: 0.88
                    }

                    MouseArea {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: 54
                        cursorShape: Qt.OpenHandCursor
                        onPressed: beginWindowDrag(mouseX, mouseY)
                        onPositionChanged: dragWindow(mouseX, mouseY)
                        onDoubleClicked: toggleMaximizeShell()
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 22
                        spacing: 16

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 14

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 4

                                Text {
                                    text: "JARVIS"
                                    color: text
                                    font.pixelSize: 34
                                    font.bold: true
                                }

                                Text {
                                    text: bridge.sceneTitle
                                    color: accent
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: "Consolas"
                                }

                                Text {
                                    text: bridge.sceneHint
                                    color: muted
                                    font.pixelSize: 12
                                }
                            }

                            RowLayout {
                                spacing: 8

                                Rectangle {
                                    width: 132
                                    height: 36
                                    radius: 18
                                    color: bridge.listenStatus === "AUTO LISTEN // ON" ? Qt.rgba(55 / 255, 247 / 255, 209 / 255, 0.14) : Qt.rgba(136 / 255, 151 / 255, 170 / 255, 0.10)
                                    border.color: bridge.listenStatus === "AUTO LISTEN // ON" ? Qt.rgba(55 / 255, 247 / 255, 209 / 255, 0.36) : Qt.rgba(136 / 255, 151 / 255, 170 / 255, 0.22)
                                    border.width: 1

                                    Text {
                                        anchors.centerIn: parent
                                        text: bridge.listenStatus === "AUTO LISTEN // ON" ? "LISTENING LIVE" : "LISTEN OFF"
                                        color: bridge.listenStatus === "AUTO LISTEN // ON" ? "#37f7d1" : muted
                                        font.pixelSize: 10
                                        font.bold: true
                                        font.family: "Consolas"
                                    }
                                }

                                Button {
                                    text: "Refresh"
                                    onClicked: bridge.refreshStatus()
                                }

                                Button {
                                    text: "Minimize"
                                    onClicked: collapseShell()
                                }

                                Button {
                                    text: shellMaximized ? "Restore" : "Maximize"
                                    onClicked: toggleMaximizeShell()
                                }
                            }
                        }

                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            Rectangle {
                                anchors.centerIn: parent
                                width: 620
                                height: 620
                                radius: 310
                                color: Qt.rgba(accent.r, accent.g, accent.b, 0.03)
                                border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.10)
                                border.width: 1
                                rotation: waveTicker.tick * 0.05
                            }

                            Rectangle {
                                anchors.centerIn: parent
                                width: 470
                                height: 470
                                radius: 235
                                color: "transparent"
                                border.color: Qt.rgba(secondaryAccent.r, secondaryAccent.g, secondaryAccent.b, 0.18)
                                border.width: 2
                                rotation: -waveTicker.tick * 0.07
                            }

                            Item {
                                anchors.horizontalCenter: parent.horizontalCenter
                                anchors.top: parent.top
                                anchors.topMargin: 44
                                width: 620
                                height: 420

                                Repeater {
                                    model: 28
                                    delegate: Rectangle {
                                        width: 2
                                        height: 64
                                        radius: 1
                                        color: Qt.rgba(accent.r, accent.g, accent.b, 0.18)
                                        anchors.centerIn: parent
                                        transform: [
                                            Translate { y: -190 },
                                            Rotation {
                                                angle: index * 12.8 + (waveTicker.tick * 0.08)
                                                origin.x: 1
                                                origin.y: 190
                                            }
                                        ]
                                    }
                                }

                                Rectangle {
                                    anchors.centerIn: parent
                                    width: 320
                                    height: 320
                                    radius: 160
                                    color: "transparent"
                                    border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.26 + statusGlowOpacity() * 0.18)
                                    border.width: 2
                                    scale: 0.94 + statusGlowOpacity() * 0.08
                                    Behavior on scale { NumberAnimation { duration: 240; easing.type: Easing.InOutQuad } }
                                }

                                Rectangle {
                                    anchors.centerIn: parent
                                    width: 228
                                    height: 228
                                    radius: 114
                                    color: "transparent"
                                    border.color: Qt.rgba(secondaryAccent.r, secondaryAccent.g, secondaryAccent.b, 0.30 + statusGlowOpacity() * 0.22)
                                    border.width: 3
                                    rotation: -waveTicker.tick * 0.28
                                }

                                Rectangle {
                                    anchors.centerIn: parent
                                    width: 142
                                    height: 142
                                    radius: 71
                                    gradient: Gradient {
                                        GradientStop { position: 0.0; color: secondaryAccent }
                                        GradientStop { position: 0.55; color: accent }
                                        GradientStop { position: 1.0; color: "#071827" }
                                    }
                                    border.color: accent
                                    border.width: 2
                                    scale: 0.92 + statusGlowOpacity() * 0.12
                                    opacity: 0.88 + statusGlowOpacity() * 0.12
                                    Behavior on scale { NumberAnimation { duration: 180; easing.type: Easing.InOutQuad } }
                                }

                                Row {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 8

                                    Repeater {
                                        model: 16
                                        delegate: Rectangle {
                                            width: 10
                                            height: signalHeight(index)
                                            radius: 5
                                            color: index % 2 === 0 ? accent : tertiaryAccent
                                            opacity: 0.24 + statusGlowOpacity() * 0.56
                                            y: (110 - height) / 2
                                            Behavior on height { NumberAnimation { duration: 140; easing.type: Easing.InOutQuad } }
                                        }
                                    }
                                }

                                Repeater {
                                    model: 18
                                    delegate: Rectangle {
                                        width: 6 + (index % 4)
                                        height: width
                                        radius: width / 2
                                        color: index % 2 === 0 ? secondaryAccent : tertiaryAccent
                                        opacity: 0.10 + (((waveTicker.tick + index * 21) % 100) / 100) * 0.22
                                        x: parent.width / 2 + Math.cos((index * 0.62) + (waveTicker.tick * 0.025)) * (118 + (index % 5) * 18) - width / 2
                                        y: parent.height / 2 + Math.sin((index * 0.74) + (waveTicker.tick * 0.020)) * (88 + (index % 4) * 16) - height / 2
                                        scale: 0.84 + (((waveTicker.tick + index * 11) % 100) / 100) * 0.5
                                    }
                                }

                                Column {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    anchors.bottom: parent.bottom
                                    anchors.bottomMargin: 20
                                    spacing: 8

                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: bridge.assistantState.toUpperCase()
                                        color: accent
                                        font.pixelSize: 13
                                        font.bold: true
                                        font.family: "Consolas"
                                    }

                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: bridge.voiceCaptureStatus
                                        color: secondaryAccent
                                        font.pixelSize: 10
                                        font.bold: true
                                        font.family: "Consolas"
                                    }
                                }
                            }

                            ColumnLayout {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                spacing: 14

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 14

                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 116
                                        radius: 22
                                        color: Qt.rgba(9 / 255, 22 / 255, 36 / 255, 0.78)
                                        border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.18)
                                        border.width: 1

                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.margins: 14
                                            spacing: 6

                                            Text {
                                                text: "HEARD"
                                                color: accent
                                                font.pixelSize: 11
                                                font.bold: true
                                                font.family: "Consolas"
                                            }

                                            Text {
                                                Layout.fillWidth: true
                                                text: bridge.lastUserTranscript
                                                color: text
                                                wrapMode: Text.WordWrap
                                                font.pixelSize: 12
                                            }
                                        }
                                    }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 116
                                        radius: 22
                                        color: Qt.rgba(9 / 255, 22 / 255, 36 / 255, 0.78)
                                        border.color: Qt.rgba(secondaryAccent.r, secondaryAccent.g, secondaryAccent.b, 0.18)
                                        border.width: 1

                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.margins: 14
                                            spacing: 6

                                            Text {
                                                text: "REPLY"
                                                color: secondaryAccent
                                                font.pixelSize: 11
                                                font.bold: true
                                                font.family: "Consolas"
                                            }

                                            Text {
                                                Layout.fillWidth: true
                                                text: bridge.lastAssistantReply
                                                color: text
                                                wrapMode: Text.WordWrap
                                                font.pixelSize: 12
                                                maximumLineCount: 4
                                                elide: Text.ElideRight
                                            }
                                        }
                                    }
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 240
                                    radius: 26
                                    color: Qt.rgba(10 / 255, 18 / 255, 31 / 255, 0.82)
                                    border.color: Qt.rgba(84 / 255, 160 / 255, 255 / 255, 0.18)
                                    border.width: 1

                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 16
                                        spacing: 10

                                        Text {
                                            text: "VISUAL RESPONSE SURFACE"
                                            color: tertiaryAccent
                                            font.pixelSize: 11
                                            font.bold: true
                                            font.family: "Consolas"
                                        }

                                        GridLayout {
                                            Layout.fillWidth: true
                                            Layout.fillHeight: true
                                            columns: 2
                                            rowSpacing: 10
                                            columnSpacing: 10

                                            Repeater {
                                                model: visualOutputModel.slice(0, 4)
                                                delegate: Rectangle {
                                                    required property var modelData
                                                    Layout.fillWidth: true
                                                    Layout.fillHeight: true
                                                    radius: 18
                                                    color: Qt.rgba(11 / 255, 26 / 255, 43 / 255, 0.72)
                                                    border.color: Qt.rgba(117 / 255, 190 / 255, 255 / 255, 0.14)
                                                    border.width: 1

                                                    ColumnLayout {
                                                        anchors.fill: parent
                                                        anchors.margins: 12
                                                        spacing: 8

                                                        Text {
                                                            text: modelData.title
                                                            color: modelData.kind === "metrics" ? tertiaryAccent : accent
                                                            font.pixelSize: 10
                                                            font.bold: true
                                                            font.family: "Consolas"
                                                        }

                                                        Loader {
                                                            Layout.fillWidth: true
                                                            Layout.fillHeight: true
                                                            property var currentData: modelData
                                                            sourceComponent: modelData.kind === "timeline" ? timelineCard : modelData.kind === "tree" ? treeCard : modelData.kind === "table" ? tableCard : modelData.kind === "metrics" ? metricsCard : textCard
                                                            onLoaded: {
                                                                if (item)
                                                                    item.payload = currentData
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    id: rightPanel
                    width: 360
                    anchors.top: parent.top
                    anchors.right: parent.right
                    anchors.bottom: dock.top
                    anchors.margins: 22
                    radius: 30
                    color: Qt.rgba(10 / 255, 18 / 255, 31 / 255, 0.72)
                    border.color: Qt.rgba(140 / 255, 194 / 255, 255 / 255, 0.16)
                    border.width: 1

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 18
                        spacing: 12

                        Text {
                            text: "LIVE CONTEXT"
                            color: tertiaryAccent
                            font.pixelSize: 12
                            font.bold: true
                            font.family: "Consolas"
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 210
                            radius: 22
                            color: Qt.rgba(11 / 255, 26 / 255, 43 / 255, 0.78)
                            border.color: Qt.rgba(95 / 255, 173 / 255, 255 / 255, 0.14)
                            border.width: 1

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 14
                                spacing: 10

                                Repeater {
                                    model: [
                                        { label: "AGENT", value: bridge.activeAgent },
                                        { label: "MODEL", value: bridge.activeModel },
                                        { label: "BACKEND", value: bridge.backendStatus },
                                        { label: "OMNIRA", value: bridge.omniraStatus },
                                        { label: "VOICE", value: bridge.voiceCaptureStatus },
                                        { label: "MEMORY", value: bridge.memoryStatus },
                                        { label: "WORKFLOW", value: bridge.workflowStatus }
                                    ]

                                    delegate: ColumnLayout {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        spacing: 2

                                        Text {
                                            text: modelData.label
                                            color: muted
                                            font.pixelSize: 9
                                            font.bold: true
                                            font.family: "Consolas"
                                        }

                                        Text {
                                            Layout.fillWidth: true
                                            text: modelData.value
                                            color: text
                                            wrapMode: Text.WordWrap
                                            font.pixelSize: 11
                                        }
                                    }
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 190
                            radius: 22
                            color: Qt.rgba(11 / 255, 26 / 255, 43 / 255, 0.78)
                            border.color: Qt.rgba(95 / 255, 173 / 255, 255 / 255, 0.14)
                            border.width: 1

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 14
                                spacing: 8

                                Text {
                                    text: "WORKFLOW TRACE"
                                    color: accent
                                    font.pixelSize: 10
                                    font.bold: true
                                    font.family: "Consolas"
                                }

                                Repeater {
                                    model: workflowTraceModel.slice(0, 5)
                                    delegate: Rectangle {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 28
                                        radius: 12
                                        color: Qt.rgba(15 / 255, 33 / 255, 56 / 255, 0.74)

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.margins: 8
                                            spacing: 8

                                            Text {
                                                text: modelData.ts
                                                color: accent
                                                font.pixelSize: 9
                                                font.family: "Consolas"
                                            }

                                            Text {
                                                text: modelData.step
                                                color: text
                                                font.pixelSize: 10
                                                font.bold: true
                                            }

                                            Item { Layout.fillWidth: true }

                                            Text {
                                                text: modelData.status.toUpperCase()
                                                color: modelData.status === "error" ? "#ff7a91" : modelData.status === "warning" ? "#ffc061" : secondaryAccent
                                                font.pixelSize: 9
                                                font.bold: true
                                                font.family: "Consolas"
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            radius: 22
                            color: Qt.rgba(11 / 255, 26 / 255, 43 / 255, 0.78)
                            border.color: Qt.rgba(95 / 255, 173 / 255, 255 / 255, 0.14)
                            border.width: 1

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 14
                                spacing: 10

                                Text {
                                    text: pendingApprovalModel.length > 0 ? "APPROVAL REQUIRED" : "RUNTIME DETAIL"
                                    color: pendingApprovalModel.length > 0 ? "#ffc061" : tertiaryAccent
                                    font.pixelSize: 10
                                    font.bold: true
                                    font.family: "Consolas"
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: pendingApprovalModel.length > 0 ? pendingApprovalModel[0].task : bridge.backendDetail
                                    color: text
                                    wrapMode: Text.WordWrap
                                    font.pixelSize: 11
                                }

                                Text {
                                    Layout.fillWidth: true
                                    visible: pendingApprovalModel.length > 0 && pendingApprovalModel[0].note.length > 0
                                    text: pendingApprovalModel.length > 0 ? pendingApprovalModel[0].note : ""
                                    color: muted
                                    wrapMode: Text.WordWrap
                                    font.pixelSize: 10
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    visible: pendingApprovalModel.length > 0

                                    Button {
                                        Layout.fillWidth: true
                                        text: "Approve"
                                        onClicked: bridge.approvePending(pendingApprovalModel[0].id)
                                    }

                                    Button {
                                        Layout.fillWidth: true
                                        text: "Reject"
                                        onClicked: bridge.rejectPending(pendingApprovalModel[0].id)
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    id: dock
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: 22
                    height: 88
                    radius: 28
                    color: Qt.rgba(8 / 255, 16 / 255, 28 / 255, 0.92)
                    border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.16)
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 14

                        Rectangle {
                            Layout.preferredWidth: 240
                            Layout.fillHeight: true
                            radius: 22
                            color: Qt.rgba(11 / 255, 26 / 255, 43 / 255, 0.78)
                            border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.16)
                            border.width: 1

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 14
                                spacing: 12

                                Rectangle {
                                    width: 52
                                    height: 52
                                    radius: 26
                                    color: Qt.rgba(accent.r, accent.g, accent.b, 0.12 + statusGlowOpacity() * 0.10)
                                    border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.26)
                                    border.width: 1

                                    Text {
                                        anchors.centerIn: parent
                                        text: bridge.listenStatus === "AUTO LISTEN // ON" ? "LIVE" : "PTT"
                                        color: text
                                        font.pixelSize: 11
                                        font.bold: true
                                        font.family: "Consolas"
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2

                                    Text {
                                        text: bridge.workflowStatus
                                        color: accent
                                        font.pixelSize: 10
                                        font.bold: true
                                        font.family: "Consolas"
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: bridge.voiceCaptureStatus
                                        color: secondaryAccent
                                        font.pixelSize: 10
                                        elide: Text.ElideRight
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: bridge.lastAssistantReply
                                        color: muted
                                        font.pixelSize: 10
                                        elide: Text.ElideRight
                                    }
                                }
                            }
                        }

                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            RowLayout {
                                anchors.centerIn: parent
                                spacing: 12

                                Repeater {
                                    model: [
                                        { label: bridge.microphoneMuted ? "Unmute microphone" : "Mute microphone", icon: bridge.microphoneMuted ? "M+" : "M-", action: "mic" },
                                        { label: bridge.speakerMuted ? "Unmute speaker" : "Mute speaker", icon: bridge.speakerMuted ? "S+" : "S-", action: "speaker" },
                                        { label: "Push to talk", icon: "PTT", action: "ptt" },
                                        { label: bridge.listenStatus === "AUTO LISTEN // ON" ? "Disable auto listen" : "Enable auto listen", icon: "AL", action: "listen" },
                                        { label: "Interrupt response", icon: "!!", action: "interrupt" },
                                        { label: bridge.textFallbackVisible ? "Hide terminal" : "Open fallback terminal", icon: ">_", action: "text" },
                                        { label: settingsVisible ? "Hide settings" : "Show settings", icon: "[]", action: "settings" }
                                    ]

                                    delegate: Button {
                                        id: actionButton
                                        required property var modelData
                                        width: 54
                                        height: 54
                                        text: modelData.icon
                                        font.pixelSize: 14
                                        font.bold: true
                                        ToolTip.visible: hovered
                                        ToolTip.delay: 200
                                        ToolTip.text: modelData.label
                                        background: Rectangle {
                                            radius: 18
                                            color: actionButton.down ? Qt.rgba(accent.r, accent.g, accent.b, 0.22) : Qt.rgba(11 / 255, 26 / 255, 43 / 255, 0.90)
                                            border.color: actionButton.hovered ? Qt.rgba(accent.r, accent.g, accent.b, 0.34) : Qt.rgba(117 / 255, 190 / 255, 255 / 255, 0.12)
                                            border.width: 1
                                        }
                                        contentItem: Text {
                                            text: actionButton.text
                                            color: text
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                            font.pixelSize: actionButton.font.pixelSize
                                            font.bold: actionButton.font.bold
                                            font.family: "Consolas"
                                        }
                                        onClicked: {
                                            if (modelData.action === "mic")
                                                bridge.toggleMicrophoneMuted()
                                            else if (modelData.action === "speaker")
                                                bridge.toggleSpeakerMuted()
                                            else if (modelData.action === "ptt")
                                                bridge.captureVoicePrompt()
                                            else if (modelData.action === "listen")
                                                bridge.setListenEnabled(bridge.listenStatus !== "AUTO LISTEN // ON")
                                            else if (modelData.action === "interrupt")
                                                bridge.interruptResponse()
                                            else if (modelData.action === "text")
                                                bridge.toggleTextFallback()
                                            else if (modelData.action === "settings")
                                                settingsVisible = !settingsVisible
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    visible: bridge.textFallbackVisible
                    width: terminalWidth
                    height: 72
                    radius: 22
                    color: Qt.rgba(9 / 255, 18 / 255, 31 / 255, 0.97)
                    border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.24)
                    border.width: 1
                    anchors.right: rightPanel.left
                    anchors.rightMargin: 18
                    anchors.bottom: dock.top
                    anchors.bottomMargin: 18

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 10

                        Rectangle {
                            width: 46
                            height: 46
                            radius: 16
                            color: Qt.rgba(secondaryAccent.r, secondaryAccent.g, secondaryAccent.b, 0.12)
                            border.color: Qt.rgba(secondaryAccent.r, secondaryAccent.g, secondaryAccent.b, 0.26)
                            border.width: 1

                            Text {
                                anchors.centerIn: parent
                                text: ">_"
                                color: text
                                font.pixelSize: 14
                                font.bold: true
                                font.family: "Consolas"
                            }
                        }

                        TextField {
                            id: promptField
                            Layout.fillWidth: true
                            placeholderText: bridge.busy ? "Jarvis is responding..." : "Fallback terminal"
                            enabled: !bridge.busy
                            color: text
                            selectByMouse: true
                            onAccepted: sendButton.clicked()
                            background: Rectangle {
                                color: "#0a1624"
                                radius: 14
                                border.color: edge
                                border.width: 1
                            }
                        }

                        Button {
                            id: sendButton
                            width: 52
                            height: 46
                            text: bridge.busy ? ".." : "GO"
                            enabled: !bridge.busy && promptField.text.trim().length > 0
                            background: Rectangle {
                                radius: 14
                                color: sendButton.enabled ? Qt.rgba(accent.r, accent.g, accent.b, 0.16) : Qt.rgba(117 / 255, 190 / 255, 255 / 255, 0.08)
                                border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.30)
                                border.width: 1
                            }
                            contentItem: Text {
                                text: sendButton.text
                                color: text
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                font.pixelSize: 12
                                font.bold: true
                                font.family: "Consolas"
                            }
                            onClicked: {
                                const value = promptField.text.trim()
                                if (!value)
                                    return
                                bridge.sendMessage(value)
                                promptField.text = ""
                            }
                        }
                    }
                }

                Rectangle {
                    visible: settingsVisible
                    width: 360
                    height: 240
                    radius: 26
                    color: Qt.rgba(9 / 255, 18 / 255, 31 / 255, 0.96)
                    border.color: Qt.rgba(148 / 255, 204 / 255, 255 / 255, 0.18)
                    border.width: 1
                    anchors.right: rightPanel.left
                    anchors.rightMargin: 18
                    anchors.bottom: dock.top
                    anchors.bottomMargin: 18

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 10

                        Text {
                            text: "SETTINGS"
                            color: tertiaryAccent
                            font.pixelSize: 11
                            font.bold: true
                            font.family: "Consolas"
                        }

                        Text {
                            text: "Startup Mode"
                            color: muted
                            font.pixelSize: 10
                            font.bold: true
                            font.family: "Consolas"
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Button {
                                Layout.fillWidth: true
                                text: bridge.launchMode === "manual" ? "Manual Start Active" : "Manual Start"
                                onClicked: bridge.setLaunchMode("manual")
                            }

                            Button {
                                Layout.fillWidth: true
                                text: bridge.launchMode === "auto-listen" ? "Auto Listen Active" : "Auto Listen Start"
                                onClicked: bridge.setLaunchMode("auto-listen")
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Button {
                                Layout.fillWidth: true
                                text: bridge.startMinimized ? "Start In Corner On" : "Start In Corner"
                                onClicked: bridge.setStartMinimized(!bridge.startMinimized)
                            }

                            Button {
                                Layout.fillWidth: true
                                text: "Close Settings"
                                onClicked: settingsVisible = false
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            text: "Manual start keeps Jarvis in the movable corner orb until invoked. Auto listen start engages live microphone mode when the shell boots."
                            color: text
                            wrapMode: Text.WordWrap
                            font.pixelSize: 11
                        }
                    }
                }
            }
        }
    }

    Component {
        id: textCard

        Text {
            property var payload
            text: payload ? payload.body : ""
            color: text
            wrapMode: Text.WordWrap
            font.pixelSize: 11
        }
    }

    Component {
        id: timelineCard

        Column {
            property var payload
            spacing: 6

            Repeater {
                model: payload ? payload.items : []
                delegate: Text {
                    required property string modelData
                    text: modelData
                    color: text
                    wrapMode: Text.WordWrap
                    font.pixelSize: 10
                }
            }
        }
    }

    Component {
        id: treeCard

        Column {
            property var payload
            spacing: 6

            Repeater {
                model: payload ? payload.items : []
                delegate: Text {
                    required property string modelData
                    text: "- " + modelData
                    color: text
                    wrapMode: Text.WordWrap
                    font.pixelSize: 10
                }
            }
        }
    }

    Component {
        id: tableCard

        Column {
            property var payload
            spacing: 6

            Repeater {
                model: payload ? payload.rows : []
                delegate: RowLayout {
                    required property var modelData
                    width: parent.width
                    spacing: 8

                    Text {
                        text: modelData[0]
                        color: muted
                        font.pixelSize: 9
                        font.bold: true
                        font.family: "Consolas"
                    }

                    Text {
                        text: modelData[1]
                        color: text
                        font.pixelSize: 10
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }
        }
    }

    Component {
        id: metricsCard

        GridLayout {
            property var payload
            columns: 2
            columnSpacing: 10
            rowSpacing: 8

            Repeater {
                model: payload ? payload.metrics : []
                delegate: Column {
                    required property var modelData
                    spacing: 2

                    Text {
                        text: modelData.label
                        color: muted
                        font.pixelSize: 9
                        font.bold: true
                        font.family: "Consolas"
                    }

                    Text {
                        text: modelData.value
                        color: text
                        font.pixelSize: 10
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }
    }
}

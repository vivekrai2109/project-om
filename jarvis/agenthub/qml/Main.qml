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
    readonly property int expandedWidth: 1080
    readonly property int expandedHeight: 760
    readonly property int terminalWidth: 430
    readonly property int terminalHeight: 420
    readonly property color accent: stateColor(bridge.assistantState)
    readonly property color secondaryAccent: bridge.assistantState === "error" ? "#ffb86a" : bridge.assistantState === "listening" ? "#42ffd7" : bridge.assistantState === "speaking" ? "#9cd0ff" : "#27c7ff"
    readonly property color tertiaryAccent: bridge.assistantState === "approval_required" ? "#ffc061" : bridge.assistantState === "error" ? "#ff8d72" : "#8ef7df"
    readonly property color glass: "#08111b"
    readonly property color glassAlt: "#0b1622"
    readonly property color edge: "#2c5673"
    readonly property color text: "#f5fbff"
    readonly property color muted: "#a2c2d9"
    readonly property var pendingApprovalModel: JSON.parse(bridge.pendingApprovalsJson)
    readonly property var workflowTraceModel: JSON.parse(bridge.workflowTraceJson)
    readonly property var visualOutputModel: JSON.parse(bridge.visualOutputJson)
    readonly property var responseEnvelopeModel: JSON.parse(bridge.responseEnvelopeJson)
    readonly property var cockpitSummaryModel: JSON.parse(bridge.cockpitSummaryJson)
    readonly property bool presenceMode: bridge.uiMode === "presence"
    readonly property bool conversationMode: bridge.uiMode === "conversation"
    readonly property bool insightMode: bridge.uiMode === "insight"
    readonly property bool operationsMode: bridge.operationsVisible
    readonly property bool approvalMode: bridge.uiMode === "approval"
    readonly property bool debugMode: bridge.uiMode === "debug"

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
        if (state === "transcribing")
            return "#71d8ff"
        if (state === "thinking")
            return "#5bc0ff"
        if (state === "speaking")
            return "#8cbeff"
        if (state === "executing")
            return "#a875ff"
        if (state === "disconnected")
            return "#6f8198"
        if (state === "muted")
            return "#8897aa"
        if (state === "error")
            return "#ff835c"
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
        if (bridge.assistantState === "transcribing")
            return 22 + ((waveTicker.tick + index * 13) % 42)
        if (bridge.assistantState === "thinking")
            return 28 + ((waveTicker.tick + index * 7) % 72)
        if (bridge.assistantState === "speaking")
            return 38 + ((waveTicker.tick * (index + 3)) % 98)
        if (bridge.assistantState === "executing")
            return 34 + ((waveTicker.tick + index * 17) % 54)
        if (bridge.assistantState === "disconnected")
            return 14 + ((index % 3) * 5)
        if (bridge.assistantState === "muted")
            return 18 + ((index % 2) * 6)
        if (bridge.assistantState === "error")
            return index % 2 === 0 ? 100 : 16
        if (bridge.assistantState === "approval_required")
            return index % 3 === 0 ? 90 : 24
        return base
    }

    function riskColor(risk) {
        if (risk === "high")
            return "#ff8f70"
        if (risk === "medium")
            return "#ffc061"
        return "#54e3c2"
    }

    function compactText(value, fallback) {
        if (value === undefined || value === null)
            return fallback
        const normalized = String(value).trim()
        return normalized.length > 0 ? normalized : fallback
    }

    function micChipText() {
        return bridge.microphoneMuted ? "OFF" : "ON"
    }

    function voiceChipText() {
        if (bridge.speakerMuted)
            return "MUTED"
        if (bridge.assistantState === "speaking")
            return "SPEAKING"
        if (bridge.assistantState === "listening" || bridge.assistantState === "transcribing")
            return "LISTENING"
        return "READY"
    }

    function omniraChipText() {
        const status = String(bridge.omniraStatus || "").toUpperCase()
        return status.indexOf("OFFLINE") >= 0 ? "OFFLINE" : "ONLINE"
    }

    function modelChipText() {
        const value = String(bridge.activeModel || "").toLowerCase()
        if (value.indexOf("14b") >= 0)
            return "QWEN 14B"
        if (value.indexOf("7b") >= 0)
            return "QWEN 7B"
        if (value.indexOf("3b") >= 0)
            return "QWEN 3B"
        if (value.indexOf("routing") >= 0)
            return "ROUTER"
        return compactText(bridge.activeModel, "MODEL")
    }

    function agentChipText() {
        const value = String(bridge.activeAgent || "").toLowerCase()
        if (value.indexOf("prime") >= 0)
            return "PRIME"
        if (value.indexOf("lite") >= 0)
            return "LITE"
        if (value.indexOf("code") >= 0)
            return "CODE"
        if (value.indexOf("research") >= 0)
            return "RESEARCH"
        if (value.indexOf("platform") >= 0)
            return "PLATFORM"
        return compactText(String(bridge.activeAgent || "").toUpperCase(), "AGENT")
    }

    function chipTone(label, value) {
        const loweredValue = String(value || "").toLowerCase()
        if (label === "MIC")
            return bridge.microphoneMuted ? "#ff8d72" : "#54e3c2"
        if (label === "VOICE")
            return bridge.speakerMuted ? "#ff8d72" : (bridge.assistantState === "speaking" ? "#9cd0ff" : "#54e3c2")
        if (label === "OMNIRA")
            return loweredValue === "offline" ? "#ff8d72" : "#54e3c2"
        return accent
    }

    function ownerAliasPreview() {
        const aliases = String(bridge.ownerAliasesText || "").split("\n").map(function(item) {
            return item.trim()
        }).filter(function(item) {
            return item.length > 0
        })
        return aliases.length > 0 ? aliases[0] : "No owner alias learned yet"
    }

    function ownerPreferencePreview() {
        const preferences = String(bridge.ownerPreferencesText || "").split("\n").map(function(item) {
            return item.trim()
        }).filter(function(item) {
            return item.length > 0
        })
        return preferences.length > 0 ? preferences[0] : "No owner preference stored yet"
    }

    function statusGlowOpacity() {
        if (bridge.assistantState === "speaking")
            return 0.72
        if (bridge.assistantState === "listening")
            return 0.62
        if (bridge.assistantState === "transcribing")
            return 0.5
        if (bridge.assistantState === "thinking")
            return 0.54
        if (bridge.assistantState === "executing")
            return 0.64
        if (bridge.assistantState === "disconnected")
            return 0.18
        if (bridge.assistantState === "muted")
            return 0.22
        if (bridge.assistantState === "error")
            return 0.48
        return 0.34
    }

    function reactorScale() {
        if (bridge.assistantState === "speaking")
            return 1.12
        if (bridge.assistantState === "listening")
            return 1.08
        if (bridge.assistantState === "transcribing")
            return 1.05
        if (bridge.assistantState === "thinking")
            return 1.04
        if (bridge.assistantState === "executing")
            return 1.06
        if (bridge.assistantState === "disconnected")
            return 0.98
        if (bridge.assistantState === "muted")
            return 0.96
        if (bridge.assistantState === "error")
            return 1.02
        if (bridge.assistantState === "approval_required")
            return 1.03
        return 1.0
    }

    function expressionOffset() {
        if (bridge.assistantState === "speaking")
            return 54
        if (bridge.assistantState === "listening")
            return 46
        if (bridge.assistantState === "transcribing")
            return 36
        if (bridge.assistantState === "thinking")
            return 32
        if (bridge.assistantState === "executing")
            return 38
        if (bridge.assistantState === "disconnected")
            return 18
        if (bridge.assistantState === "muted")
            return 16
        if (bridge.assistantState === "error")
            return 12
        if (bridge.assistantState === "approval_required")
            return 22
        return 26
    }

    function voiceMuted() {
        return bridge.microphoneMuted || bridge.speakerMuted
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
            if (JSON.parse(bridge.pendingApprovalsJson).length > 0) {
                expandShell()
                bridge.showApproval("Pending supervised action")
            }
        }

        function onStartMinimizedChanged() {
            if (!bridge.startMinimized)
                expandShell()
        }

        function onUiModeChanged() {
            if (bridge.operationsVisible)
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
            color: "transparent"

            Rectangle {
                width: shellExpanded ? 460 : 120
                height: width
                radius: width / 2
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: shellExpanded ? -150 : -24
                color: Qt.rgba(accent.r, accent.g, accent.b, shellExpanded ? 0.08 : 0.12)
                opacity: 0.7
                layer.enabled: true
            }

            Rectangle {
                width: shellExpanded ? 540 : 100
                height: width
                radius: width / 2
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.rightMargin: shellExpanded ? -180 : -20
                anchors.bottomMargin: shellExpanded ? -220 : -20
                color: Qt.rgba(tertiaryAccent.r, tertiaryAccent.g, tertiaryAccent.b, shellExpanded ? 0.06 : 0.08)
                opacity: 0.65
                layer.enabled: true
            }
        }

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            gradient: Gradient {
                GradientStop { position: 0.0; color: shellExpanded ? "#0a1420" : "#08111a" }
                GradientStop { position: 0.48; color: shellExpanded ? "#06101a" : "#050d16" }
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

            Rectangle {
                anchors.centerIn: parent
                width: 16
                height: 16
                radius: 8
                color: Qt.rgba(text.r, text.g, text.b, 0.88)
                opacity: 0.78 + statusGlowOpacity() * 0.18
            }

            Rectangle {
                visible: bridge.listenStatus === "AUTO LISTEN // ON"
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 8
                width: 10
                height: 10
                radius: 5
                color: "#37f7d1"
                border.color: Qt.rgba(55 / 255, 247 / 255, 209 / 255, 0.44)
                border.width: 1
                opacity: 0.55 + statusGlowOpacity() * 0.4
            }

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: 10
                text: voiceMuted() ? "MUTED" : (bridge.listenStatus === "AUTO LISTEN // ON" ? "LIVE" : "READY")
                color: voiceMuted() ? "#ff9daa" : text
                font.pixelSize: 9
                font.bold: true
                font.family: "Consolas"
                opacity: 0.88
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
                    anchors.fill: parent
                    anchors.margins: 22
                    radius: 30
                    color: Qt.rgba(8 / 255, 16 / 255, 28 / 255, 0.28)
                    border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.12)
                    border.width: 1
                }

                MouseArea {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    height: 96
                    cursorShape: Qt.OpenHandCursor
                    onPressed: beginWindowDrag(mouseX, mouseY)
                    onPositionChanged: dragWindow(mouseX, mouseY)
                    onDoubleClicked: toggleMaximizeShell()
                }

                Item {
                    anchors.fill: parent
                    anchors.leftMargin: 36
                    anchors.rightMargin: 36
                    anchors.topMargin: 28
                    anchors.bottomMargin: 124

                    Rectangle {
                        anchors.centerIn: parent
                        width: 720
                        height: 720
                        radius: 360
                        color: Qt.rgba(accent.r, accent.g, accent.b, 0.032 + statusGlowOpacity() * 0.03)
                        border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.12)
                        border.width: 1
                        rotation: waveTicker.tick * 0.03
                        layer.enabled: true
                    }

                    Rectangle {
                        anchors.centerIn: parent
                        width: bridge.assistantState === "listening" ? 596 + ((waveTicker.tick % 14) * 2) : 556
                        height: width
                        radius: width / 2
                        color: "transparent"
                        border.color: Qt.rgba(secondaryAccent.r, secondaryAccent.g, secondaryAccent.b, bridge.assistantState === "listening" ? 0.34 : 0.20 + statusGlowOpacity() * 0.12)
                        border.width: bridge.assistantState === "listening" ? 3 : 2
                        rotation: bridge.assistantState === "thinking" ? -waveTicker.tick * 0.16 : -waveTicker.tick * 0.06
                        opacity: bridge.assistantState === "muted" ? 0.36 : 1.0
                    }

                    Rectangle {
                        anchors.centerIn: parent
                        width: 480
                        height: 480
                        radius: 240
                        color: "transparent"
                        border.color: Qt.rgba(text.r, text.g, text.b, bridge.assistantState === "executing" ? 0.24 : 0.08)
                        border.width: bridge.assistantState === "executing" ? 2 : 1
                        rotation: bridge.assistantState === "executing" ? waveTicker.tick * 0.25 : 0
                    }

                    Repeater {
                        visible: bridge.assistantState === "executing"
                        model: 36
                        delegate: Rectangle {
                            width: 5
                            height: 22
                            radius: 2
                            color: Qt.rgba(accent.r, accent.g, accent.b, ((index + (waveTicker.tick % 36)) % 36) < 18 ? 0.72 : 0.16)
                            anchors.centerIn: parent
                            transform: [
                                Translate { y: -228 },
                                Rotation {
                                    angle: index * 10
                                    origin.x: 2.5
                                    origin.y: 228
                                }
                            ]
                        }
                    }

                    Repeater {
                        model: 32
                        delegate: Rectangle {
                            width: 2
                            height: 72 + (index % 4) * 10
                            radius: 1
                            color: Qt.rgba(accent.r, accent.g, accent.b, 0.08 + statusGlowOpacity() * 0.12)
                            anchors.centerIn: parent
                            transform: [
                                Translate { y: -250 },
                                Rotation {
                                    angle: index * 11.25 + (waveTicker.tick * 0.05)
                                    origin.x: 1
                                    origin.y: 250
                                }
                            ]
                        }
                    }

                    Repeater {
                        model: 24
                        delegate: Rectangle {
                            width: 4
                            height: 116 + (index % 4) * 10
                            radius: 2
                            color: Qt.rgba(accent.r, accent.g, accent.b, 0.14 + statusGlowOpacity() * 0.14)
                            anchors.centerIn: parent
                            transform: [
                                Translate { y: -286 },
                                Rotation {
                                    angle: index * 15 + waveTicker.tick * 0.12
                                    origin.x: 2
                                    origin.y: 286
                                }
                            ]
                        }
                    }

                    Repeater {
                        model: 12
                        delegate: Rectangle {
                            width: 74
                            height: 16
                            radius: 8
                            gradient: Gradient {
                                GradientStop { position: 0.0; color: Qt.rgba(secondaryAccent.r, secondaryAccent.g, secondaryAccent.b, 0.0) }
                                GradientStop { position: 0.3; color: Qt.rgba(secondaryAccent.r, secondaryAccent.g, secondaryAccent.b, 0.24) }
                                GradientStop { position: 0.7; color: Qt.rgba(accent.r, accent.g, accent.b, 0.52) }
                                GradientStop { position: 1.0; color: Qt.rgba(accent.r, accent.g, accent.b, 0.0) }
                            }
                            anchors.centerIn: parent
                            opacity: 0.42 + statusGlowOpacity() * 0.22
                            transform: [
                                Translate { y: -326 },
                                Rotation {
                                    angle: index * 30 - waveTicker.tick * 0.08
                                    origin.x: 37
                                    origin.y: 326
                                }
                            ]
                        }
                    }

                    Repeater {
                        model: 18
                        delegate: Rectangle {
                            width: 6 + (index % 3) * 3
                            height: width
                            radius: width / 2
                            color: index % 2 === 0 ? secondaryAccent : tertiaryAccent
                            opacity: 0.16 + (((waveTicker.tick + index * 17) % 100) / 100) * 0.22
                            x: parent.width / 2 + Math.cos((index * 0.74) + (waveTicker.tick * 0.018)) * (170 + (index % 4) * 18) - width / 2
                            y: parent.height / 2 + Math.sin((index * 0.52) + (waveTicker.tick * 0.015)) * (142 + (index % 5) * 15) - height / 2
                            scale: 0.8 + (((waveTicker.tick + index * 9) % 100) / 100) * 0.6
                        }
                    }

                    Item {
                        anchors.centerIn: parent
                        width: 420
                        height: 420
                        scale: reactorScale()
                        Behavior on scale { NumberAnimation { duration: 220; easing.type: Easing.InOutQuad } }

                        Timer {
                            id: reactorTapTimer
                            interval: 220
                            repeat: false
                            onTriggered: {
                                if (!reactorMouse.pendingToggle)
                                    return
                                reactorMouse.pendingToggle = false
                                if (voiceMuted()) {
                                    if (bridge.microphoneMuted)
                                        bridge.toggleMicrophoneMuted()
                                    if (bridge.speakerMuted)
                                        bridge.toggleSpeakerMuted()
                                } else {
                                    bridge.toggleMicrophoneMuted()
                                    bridge.toggleSpeakerMuted()
                                }
                            }
                        }

                        MouseArea {
                            id: reactorMouse
                            anchors.fill: parent
                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                            property bool pendingToggle: false
                            onClicked: function(mouse) {
                                if (mouse.button === Qt.RightButton) {
                                    bridge.toggleTextFallback()
                                    return
                                }
                                pendingToggle = true
                                reactorTapTimer.restart()
                            }
                            onDoubleClicked: function(mouse) {
                                if (mouse.button !== Qt.LeftButton)
                                    return
                                pendingToggle = false
                                reactorTapTimer.stop()
                                collapseShell()
                            }
                        }

                        Rectangle {
                            anchors.centerIn: parent
                            width: 420
                            height: 420
                            radius: 210
                            color: "transparent"
                            border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.34 + statusGlowOpacity() * 0.18)
                            border.width: 2
                        }

                        Rectangle {
                            anchors.centerIn: parent
                            width: 308
                            height: 308
                            radius: 154
                            color: "transparent"
                            border.color: Qt.rgba(secondaryAccent.r, secondaryAccent.g, secondaryAccent.b, 0.38 + statusGlowOpacity() * 0.22)
                            border.width: 3
                            rotation: bridge.assistantState === "thinking" ? -waveTicker.tick * 0.34 : -waveTicker.tick * 0.22
                        }

                        Rectangle {
                            anchors.centerIn: parent
                            width: 196
                            height: 196
                            radius: 98
                            gradient: Gradient {
                                GradientStop { position: 0.0; color: Qt.rgba(secondaryAccent.r, secondaryAccent.g, secondaryAccent.b, bridge.assistantState === "muted" ? 0.36 : 0.98) }
                                GradientStop { position: 0.50; color: Qt.rgba(accent.r, accent.g, accent.b, bridge.assistantState === "muted" ? 0.24 : 0.92) }
                                GradientStop { position: 1.0; color: "#061420" }
                            }
                            border.color: Qt.rgba(text.r, text.g, text.b, 0.30)
                            border.width: 2
                            opacity: bridge.assistantState === "muted" ? 0.42 : 0.88 + statusGlowOpacity() * 0.18
                            layer.enabled: true
                        }

                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.verticalCenter: parent.verticalCenter
                            y: -118 - expressionOffset()
                            width: 250
                            height: 54
                            radius: 27
                            color: Qt.rgba(3 / 255, 10 / 255, 18 / 255, 0.86)
                            border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.22)
                            border.width: 1
                            opacity: 0.78
                            rotation: -4
                            Behavior on y { NumberAnimation { duration: 220; easing.type: Easing.InOutQuad } }
                        }

                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.verticalCenter: parent.verticalCenter
                            y: 64 + expressionOffset()
                            width: 250
                            height: 54
                            radius: 27
                            color: Qt.rgba(3 / 255, 10 / 255, 18 / 255, 0.86)
                            border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.22)
                            border.width: 1
                            opacity: 0.78
                            rotation: 4
                            Behavior on y { NumberAnimation { duration: 220; easing.type: Easing.InOutQuad } }
                        }

                        Row {
                            anchors.centerIn: parent
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
                            model: 10
                            delegate: Rectangle {
                                width: 12
                                height: 12
                                radius: 6
                                color: index % 2 === 0 ? secondaryAccent : accent
                                opacity: 0.3 + (((waveTicker.tick + index * 13) % 100) / 100) * 0.4
                                x: parent.width / 2 + Math.cos(index * 0.628 + (waveTicker.tick * 0.02)) * 130 - width / 2
                                y: parent.height / 2 + Math.sin(index * 0.628 + (waveTicker.tick * 0.02)) * 130 - height / 2
                            }
                        }

                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.top: parent.top
                            anchors.topMargin: 18
                            width: 220
                            height: 38
                            radius: 21
                            color: Qt.rgba(4 / 255, 11 / 255, 20 / 255, 0.90)
                            border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.24)
                            border.width: 1

                            Row {
                                anchors.centerIn: parent
                                spacing: 10

                                Text {
                                    text: voiceMuted() ? "VOICE MUTED" : (bridge.listenStatus === "AUTO LISTEN // ON" ? "ACTIVE LISTEN" : "VOICE READY")
                                    color: voiceMuted() ? "#ff9daa" : text
                                    font.pixelSize: 10
                                    font.bold: true
                                    font.family: "Consolas"
                                }

                                Text {
                                    text: bridge.ownerKnown ? ("OWNER " + bridge.ownerName.toUpperCase()) : "OWNER UNKNOWN"
                                    color: muted
                                    font.pixelSize: 10
                                    font.bold: true
                                    font.family: "Consolas"
                                }
                            }
                        }
                    }

                    Rectangle {
                        visible: !presenceMode && !operationsMode
                        width: 260
                        height: 146
                        radius: 24
                        anchors.left: parent.left
                        anchors.leftMargin: 48
                        anchors.top: parent.top
                        anchors.topMargin: 84
                        color: Qt.rgba(6 / 255, 14 / 255, 26 / 255, 0.78)
                        border.color: Qt.rgba(secondaryAccent.r, secondaryAccent.g, secondaryAccent.b, 0.18)
                        border.width: 1

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 8

                            Text {
                                text: "HEARD"
                                color: tertiaryAccent
                                font.pixelSize: 10
                                font.bold: true
                                font.family: "Consolas"
                            }

                            Text {
                                Layout.fillWidth: true
                                text: bridge.voiceCaptureStatus
                                color: secondaryAccent
                                wrapMode: Text.WordWrap
                                maximumLineCount: 2
                                elide: Text.ElideRight
                                font.pixelSize: 11
                                font.bold: true
                                font.family: "Consolas"
                            }

                            Text {
                                Layout.fillWidth: true
                                text: bridge.lastUserTranscript
                                color: text
                                wrapMode: Text.WordWrap
                                maximumLineCount: 4
                                elide: Text.ElideRight
                                font.pixelSize: 13
                            }
                        }
                    }

                    Rectangle {
                        visible: !presenceMode && !approvalMode
                        width: 300
                        height: 168
                        radius: 24
                        anchors.right: parent.right
                        anchors.rightMargin: 42
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 136
                        color: Qt.rgba(7 / 255, 15 / 255, 28 / 255, 0.78)
                        border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.18)
                        border.width: 1

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 8

                            Text {
                                text: "JARVIS"
                                color: accent
                                font.pixelSize: 10
                                font.bold: true
                                font.family: "Consolas"
                            }

                            Text {
                                Layout.fillWidth: true
                                text: bridge.lastAssistantReply
                                color: text
                                wrapMode: Text.WordWrap
                                maximumLineCount: 5
                                elide: Text.ElideRight
                                font.pixelSize: 13
                            }
                        }
                    }

                    Rectangle {
                        visible: bridge.ownerKnown && !presenceMode && !approvalMode
                        width: 304
                        height: 176
                        radius: 24
                        anchors.right: parent.right
                        anchors.rightMargin: 52
                        anchors.top: parent.top
                        anchors.topMargin: 146
                        color: Qt.rgba(7 / 255, 15 / 255, 28 / 255, 0.82)
                        border.color: Qt.rgba(secondaryAccent.r, secondaryAccent.g, secondaryAccent.b, 0.20)
                        border.width: 1

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 8

                            Text {
                                text: "OWNER PRESENCE"
                                color: tertiaryAccent
                                font.pixelSize: 10
                                font.bold: true
                                font.family: "Consolas"
                            }

                            Text {
                                Layout.fillWidth: true
                                text: bridge.ownerName.toUpperCase()
                                color: text
                                font.pixelSize: 20
                                font.bold: true
                                elide: Text.ElideRight
                            }

                            Text {
                                Layout.fillWidth: true
                                text: ownerAliasPreview()
                                color: muted
                                wrapMode: Text.WordWrap
                                maximumLineCount: 2
                                elide: Text.ElideRight
                                font.pixelSize: 11
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 30
                                    radius: 15
                                    color: Qt.rgba(11 / 255, 24 / 255, 40 / 255, 0.88)
                                    border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.18)
                                    border.width: 1

                                    Text {
                                        anchors.centerIn: parent
                                        text: bridge.cameraConsent ? "CAMERA CONSENT ON" : "CAMERA CONSENT OFF"
                                        color: bridge.cameraConsent ? secondaryAccent : muted
                                        font.pixelSize: 9
                                        font.bold: true
                                        font.family: "Consolas"
                                    }
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 30
                                    radius: 15
                                    color: Qt.rgba(11 / 255, 24 / 255, 40 / 255, 0.88)
                                    border.color: Qt.rgba(secondaryAccent.r, secondaryAccent.g, secondaryAccent.b, 0.18)
                                    border.width: 1

                                    Text {
                                        anchors.centerIn: parent
                                        text: bridge.voiceLearningEnabled ? "VOICE LEARN ON" : "VOICE LEARN OFF"
                                        color: bridge.voiceLearningEnabled ? accent : muted
                                        font.pixelSize: 9
                                        font.bold: true
                                        font.family: "Consolas"
                                    }
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: ownerPreferencePreview()
                                color: text
                                wrapMode: Text.WordWrap
                                maximumLineCount: 3
                                elide: Text.ElideRight
                                font.pixelSize: 12
                            }
                        }
                    }

                    Rectangle {
                        visible: operationsMode && !presenceMode
                        width: 270
                        height: 118
                        radius: 22
                        anchors.left: parent.left
                        anchors.leftMargin: 48
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 150
                        color: Qt.rgba(7 / 255, 15 / 255, 28 / 255, 0.78)
                        border.color: Qt.rgba(tertiaryAccent.r, tertiaryAccent.g, tertiaryAccent.b, 0.18)
                        border.width: 1

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 8

                            Text {
                                text: "TELEMETRY"
                                color: tertiaryAccent
                                font.pixelSize: 10
                                font.bold: true
                                font.family: "Consolas"
                            }

                            Text {
                                Layout.fillWidth: true
                                text: bridge.routeSummary
                                color: text
                                wrapMode: Text.WordWrap
                                maximumLineCount: 2
                                elide: Text.ElideRight
                                font.pixelSize: 11
                                font.bold: true
                                font.family: "Consolas"
                            }

                            Text {
                                Layout.fillWidth: true
                                text: bridge.latencySummary
                                color: secondaryAccent
                                wrapMode: Text.WordWrap
                                maximumLineCount: 2
                                elide: Text.ElideRight
                                font.pixelSize: 11
                                font.bold: true
                                font.family: "Consolas"
                            }
                        }
                    }

                    Rectangle {
                        visible: !bridge.ownerKnown
                        width: 420
                        height: 214
                        radius: 28
                        color: Qt.rgba(6 / 255, 14 / 255, 25 / 255, 0.96)
                        border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.22)
                        border.width: 1
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.verticalCenter: parent.verticalCenter

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 20
                            spacing: 10

                            Text {
                                text: "OWNER BINDING"
                                color: tertiaryAccent
                                font.pixelSize: 11
                                font.bold: true
                                font.family: "Consolas"
                            }

                            Text {
                                Layout.fillWidth: true
                                text: "Tell Jarvis who owns this shell. This enables welcome behavior and local personalization."
                                color: text
                                wrapMode: Text.WordWrap
                                font.pixelSize: 14
                            }

                            TextField {
                                id: ownerNameField
                                Layout.fillWidth: true
                                placeholderText: "Your name"
                                placeholderTextColor: muted
                                text: bridge.ownerName
                                enabled: !bridge.busy
                                color: text
                                selectedTextColor: glass
                                selectionColor: accent
                                font.pixelSize: 14
                                font.family: "Segoe UI"
                                selectByMouse: true
                                onAccepted: ownerBindButton.clicked()
                                background: Rectangle {
                                    color: "#0a1624"
                                    radius: 14
                                    border.color: edge
                                    border.width: 1
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                Button {
                                    id: ownerBindButton
                                    Layout.fillWidth: true
                                    text: "Bind Owner"
                                    enabled: ownerNameField.text.trim().length > 0 && !bridge.busy
                                    onClicked: bridge.setOwnerName(ownerNameField.text)
                                }

                                Button {
                                    Layout.fillWidth: true
                                    text: "Use Voice"
                                    enabled: !bridge.busy
                                    onClicked: bridge.captureVoicePrompt()
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: "Camera recognition is not wired yet. This local owner profile is the first identity layer."
                                color: muted
                                wrapMode: Text.WordWrap
                                font.pixelSize: 11
                            }
                        }
                    }

                    Rectangle {
                        width: presenceMode ? 620 : 640
                        height: presenceMode ? 64 : 116
                        radius: 28
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: presenceMode ? 138 : 128
                        color: Qt.rgba(5 / 255, 12 / 255, 21 / 255, presenceMode ? 0.90 : 0.9)
                        border.color: Qt.rgba(accent.r, accent.g, accent.b, presenceMode ? 0.24 : 0.2)
                        border.width: 1

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: presenceMode ? 14 : 16
                            spacing: presenceMode ? 4 : 6

                            Text {
                                Layout.fillWidth: true
                                text: bridge.assistantState === "listening" || bridge.assistantState === "transcribing" ? "LIVE TRANSCRIPT" : "VOICE RESPONSE"
                                color: bridge.assistantState === "listening" || bridge.assistantState === "transcribing" ? tertiaryAccent : accent
                                font.pixelSize: 10
                                font.bold: true
                                font.family: "Consolas"
                            }

                            Text {
                                Layout.fillWidth: true
                                text: bridge.assistantState === "listening" || bridge.assistantState === "transcribing" ? bridge.lastUserTranscript : bridge.lastAssistantReply
                                color: text
                                wrapMode: Text.WordWrap
                                maximumLineCount: presenceMode ? 1 : 4
                                elide: Text.ElideRight
                                font.pixelSize: presenceMode ? 14 : 14
                                font.bold: presenceMode
                            }
                        }
                    }

                    Rectangle {
                        width: 760
                        height: 58
                        radius: 29
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.top: parent.top
                        anchors.topMargin: 22
                        color: Qt.rgba(5 / 255, 12 / 255, 21 / 255, 0.88)
                        border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.22)
                        border.width: 1

                        Row {
                            anchors.centerIn: parent
                            spacing: 12

                            Repeater {
                                model: [
                                    { label: "MIC", value: micChipText() },
                                    { label: "VOICE", value: voiceChipText() },
                                    { label: "OMNIRA", value: omniraChipText() },
                                    { label: "MODEL", value: modelChipText() },
                                    { label: "AGENT", value: agentChipText() }
                                ]

                                delegate: Rectangle {
                                    required property var modelData
                                    width: modelData.label === "MODEL" ? 154 : 116
                                    height: 40
                                    radius: 20
                                    color: Qt.rgba(11 / 255, 24 / 255, 40 / 255, 0.94)
                                    border.color: Qt.rgba(Qt.color(chipTone(modelData.label, modelData.value)).r, Qt.color(chipTone(modelData.label, modelData.value)).g, Qt.color(chipTone(modelData.label, modelData.value)).b, 0.34)
                                    border.width: 1

                                    Column {
                                        anchors.fill: parent
                                        anchors.margins: 7
                                        spacing: 2

                                        Text {
                                            text: modelData.label
                                            color: muted
                                            font.pixelSize: 8
                                            font.bold: true
                                            font.family: "Consolas"
                                        }

                                        Text {
                                            text: modelData.value
                                            color: text
                                            font.pixelSize: 11
                                            font.bold: true
                                            font.family: "Consolas"
                                            elide: Text.ElideRight
                                            width: parent.width
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        visible: presenceMode
                        width: 260
                        height: 34
                        radius: 17
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.top: parent.top
                        anchors.topMargin: 88
                        color: Qt.rgba(7 / 255, 17 / 255, 28 / 255, 0.84)
                        border.color: Qt.rgba(148 / 255, 204 / 255, 255 / 255, 0.16)
                        border.width: 1

                        Row {
                            anchors.centerIn: parent
                            spacing: 8

                            Rectangle {
                                width: 8
                                height: 8
                                radius: 4
                                color: bridge.ownerKnown ? secondaryAccent : muted
                            }

                            Text {
                                text: bridge.ownerKnown ? ("OWNER // " + bridge.ownerName.toUpperCase()) : compactText(bridge.sceneTitle, "STANDBY")
                                color: text
                                font.pixelSize: 10
                                font.bold: true
                                font.family: "Consolas"
                            }
                        }
                    }
                }

                Item {
                    anchors.top: parent.top
                    anchors.right: parent.right
                    anchors.topMargin: 26
                    anchors.rightMargin: 26
                    width: 160
                    height: 48

                    Row {
                        anchors.right: parent.right
                        spacing: 10

                        Repeater {
                            model: [
                                { label: "Refresh status", icon: "o", action: "refresh" },
                                { label: "Collapse shell", icon: "_", action: "collapse" },
                                { label: shellMaximized ? "Restore shell" : "Maximize shell", icon: shellMaximized ? "<>" : "[]", action: "maximize" }
                            ]

                            delegate: Button {
                                id: chromeButton
                                required property var modelData
                                width: 40
                                height: 40
                                text: modelData.icon
                                font.pixelSize: 12
                                font.bold: true
                                ToolTip.visible: hovered
                                ToolTip.delay: 200
                                ToolTip.text: modelData.label
                                background: Rectangle {
                                    radius: 20
                                    color: chromeButton.down ? Qt.rgba(accent.r, accent.g, accent.b, 0.22) : Qt.rgba(11 / 255, 26 / 255, 43 / 255, 0.84)
                                    border.color: chromeButton.hovered ? Qt.rgba(accent.r, accent.g, accent.b, 0.34) : Qt.rgba(117 / 255, 190 / 255, 255 / 255, 0.12)
                                    border.width: 1
                                }
                                contentItem: Text {
                                    text: chromeButton.text
                                    color: text
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    font.pixelSize: chromeButton.font.pixelSize
                                    font.bold: chromeButton.font.bold
                                    font.family: "Consolas"
                                }
                                onClicked: {
                                    if (modelData.action === "refresh")
                                        bridge.refreshStatus()
                                    else if (modelData.action === "collapse")
                                        collapseShell()
                                    else if (modelData.action === "maximize")
                                        toggleMaximizeShell()
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    visible: pendingApprovalModel.length > 0
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.leftMargin: 26
                    anchors.topMargin: 26
                    width: 104
                    height: 44
                    radius: 22
                    color: Qt.rgba(31 / 255, 23 / 255, 10 / 255, 0.92)
                    border.color: Qt.rgba(255 / 255, 192 / 255, 97 / 255, 0.34)
                    border.width: 1

                    Row {
                        anchors.centerIn: parent
                        spacing: 10

                        Repeater {
                            model: [
                                { label: "Approve pending action", icon: "Y", action: "approve" },
                                { label: "Reject pending action", icon: "N", action: "reject" }
                            ]

                            delegate: Button {
                                id: approvalButton
                                required property var modelData
                                width: 34
                                height: 34
                                text: modelData.icon
                                font.pixelSize: 11
                                font.bold: true
                                ToolTip.visible: hovered
                                ToolTip.delay: 200
                                ToolTip.text: modelData.label
                                background: Rectangle {
                                    radius: 17
                                    color: approvalButton.down ? Qt.rgba(255 / 255, 192 / 255, 97 / 255, 0.24) : Qt.rgba(39 / 255, 28 / 255, 12 / 255, 0.9)
                                    border.color: Qt.rgba(255 / 255, 192 / 255, 97 / 255, 0.24)
                                    border.width: 1
                                }
                                contentItem: Text {
                                    text: approvalButton.text
                                    color: text
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    font.pixelSize: approvalButton.font.pixelSize
                                    font.bold: approvalButton.font.bold
                                    font.family: "Consolas"
                                }
                                onClicked: {
                                    if (pendingApprovalModel.length === 0)
                                        return
                                    if (modelData.action === "approve")
                                        bridge.approvePending(pendingApprovalModel[0].id)
                                    else if (modelData.action === "reject")
                                        bridge.rejectPending(pendingApprovalModel[0].id)
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    id: operationsDrawer
                    visible: bridge.operationsVisible
                    width: 356
                    height: 670
                    radius: 28
                    color: Qt.rgba(7 / 255, 15 / 255, 28 / 255, 0.97)
                    border.color: approvalMode ? Qt.rgba(255 / 255, 192 / 255, 97 / 255, 0.28) : Qt.rgba(accent.r, accent.g, accent.b, 0.18)
                    border.width: 1
                    anchors.right: parent.right
                    anchors.rightMargin: 26
                    anchors.bottom: dock.top
                    anchors.bottomMargin: 18

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 10

                        RowLayout {
                            Layout.fillWidth: true

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2

                                Text {
                                    text: debugMode ? "DEBUG" : (approvalMode ? "APPROVAL" : "OPERATIONS")
                                    color: approvalMode ? tertiaryAccent : accent
                                    font.pixelSize: 11
                                    font.bold: true
                                    font.family: "Consolas"
                                }

                                Text {
                                    text: approvalMode ? "Approval state and task context." : (debugMode ? "Low-level runtime visibility enabled." : "Jarvis cockpit with live model, route, language, and learning visibility.")
                                    color: muted
                                    wrapMode: Text.WordWrap
                                    font.pixelSize: 11
                                }
                            }

                            Button {
                                visible: !approvalMode && !debugMode
                                text: "Hide"
                                onClicked: bridge.hideOperations()
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 118
                            radius: 18
                            color: "#0a1624"
                            border.color: edge
                            border.width: 1

                            GridLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                columns: 3
                                rowSpacing: 8
                                columnSpacing: 10

                                Repeater {
                                    model: [
                                        { label: "Turns", value: cockpitSummaryModel.learning ? String(cockpitSummaryModel.learning.interactions_today) : "0" },
                                        { label: "Learned", value: cockpitSummaryModel.learning ? String(cockpitSummaryModel.learning.learning_records_today) : "0" },
                                        { label: "Candidates", value: cockpitSummaryModel.learning ? String(cockpitSummaryModel.learning.training_candidates_today) : "0" },
                                        { label: "Tools", value: cockpitSummaryModel.learning ? String(cockpitSummaryModel.learning.tool_calls_today) : "0" },
                                        { label: "Compute", value: cockpitSummaryModel.controls ? cockpitSummaryModel.controls.compute_mode : "balanced" },
                                        { label: "Pinned", value: cockpitSummaryModel.controls && cockpitSummaryModel.controls.pinned_model ? cockpitSummaryModel.controls.pinned_model : "dynamic" }
                                    ]

                                    delegate: Column {
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
                                            text: modelData.value
                                            color: text
                                            font.pixelSize: 13
                                            font.bold: true
                                            wrapMode: Text.WordWrap
                                            maximumLineCount: 2
                                        }
                                    }
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: approvalMode && pendingApprovalModel.length > 0 ? 96 : 0
                            visible: approvalMode && pendingApprovalModel.length > 0
                            radius: 18
                            color: Qt.rgba(39 / 255, 28 / 255, 12 / 255, 0.92)
                            border.color: Qt.rgba(255 / 255, 192 / 255, 97 / 255, 0.24)
                            border.width: 1

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 6

                                Text {
                                    Layout.fillWidth: true
                                    text: pendingApprovalModel.length > 0 ? pendingApprovalModel[0].task : ""
                                    color: text
                                    wrapMode: Text.WordWrap
                                    maximumLineCount: 3
                                    elide: Text.ElideRight
                                    font.pixelSize: 12
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Button {
                                        Layout.fillWidth: true
                                        text: "Approve"
                                        onClicked: if (pendingApprovalModel.length > 0) bridge.approvePending(pendingApprovalModel[0].id)
                                    }

                                    Button {
                                        Layout.fillWidth: true
                                        text: "Reject"
                                        onClicked: if (pendingApprovalModel.length > 0) bridge.rejectPending(pendingApprovalModel[0].id)
                                    }
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 92
                            radius: 18
                            color: "#0a1624"
                            border.color: edge
                            border.width: 1

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 6

                                Text {
                                    text: "CURRENT REPLY"
                                    color: accent
                                    font.pixelSize: 10
                                    font.bold: true
                                    font.family: "Consolas"
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: compactText(responseEnvelopeModel.reply_text, bridge.lastAssistantReply)
                                    color: text
                                    wrapMode: Text.WordWrap
                                    maximumLineCount: 4
                                    elide: Text.ElideRight
                                    font.pixelSize: 12
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 180
                            radius: 18
                            color: "#0a1624"
                            border.color: edge
                            border.width: 1

                            GridLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                columns: 2
                                rowSpacing: 8
                                columnSpacing: 12

                                Repeater {
                                    model: [
                                        { label: "Agent", value: responseEnvelopeModel.agent || bridge.activeAgent },
                                        { label: "Model", value: responseEnvelopeModel.model || bridge.activeModel },
                                        { label: "Provider", value: responseEnvelopeModel.provider || "unknown" },
                                        { label: "Backend", value: bridge.backendStatus },
                                        { label: "OMNIRA", value: bridge.omniraStatus },
                                        { label: "Risk", value: (responseEnvelopeModel.risk_level || "low").toUpperCase() },
                                        { label: "Approval", value: responseEnvelopeModel.approval_required ? "REQUIRED" : "CLEAR" },
                                        { label: "Voice", value: bridge.voiceCaptureStatus.replace("VOICE // ", "") },
                                        { label: "Memory", value: responseEnvelopeModel.memory_hits ? String(responseEnvelopeModel.memory_hits.length) : "0" },
                                        { label: "Workflow", value: bridge.workflowStatus.replace("WORKFLOW // ", "") },
                                        { label: "Route", value: responseEnvelopeModel.decision_path && responseEnvelopeModel.decision_path.length > 0 ? responseEnvelopeModel.decision_path.join(" > ") : bridge.routeSummary }
                                    ]

                                    delegate: Column {
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
                                            text: modelData.value
                                            color: text
                                            font.pixelSize: 10
                                            wrapMode: Text.WordWrap
                                            maximumLineCount: 2
                                            elide: Text.ElideRight
                                            width: 140
                                        }
                                    }
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 94
                            radius: 18
                            color: "#0a1624"
                            border.color: edge
                            border.width: 1

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 6

                                Text {
                                    text: "LANGUAGE AND VOICE"
                                    color: tertiaryAccent
                                    font.pixelSize: 10
                                    font.bold: true
                                    font.family: "Consolas"
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Button {
                                        Layout.fillWidth: true
                                        text: bridge.speechModeSummary.indexOf("ENGLISH") >= 0 ? "English Active" : "English"
                                        onClicked: bridge.setSpeechLanguageMode("english")
                                    }

                                    Button {
                                        Layout.fillWidth: true
                                        text: bridge.speechModeSummary.indexOf("HINGLISH") >= 0 ? "Hinglish Active" : "Hinglish"
                                        onClicked: bridge.setSpeechLanguageMode("hinglish")
                                    }

                                    Button {
                                        Layout.fillWidth: true
                                        text: bridge.speechModeSummary.indexOf("HINDI") >= 0 ? "Hindi Active" : "Hindi"
                                        onClicked: bridge.setSpeechLanguageMode("hindi")
                                    }
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: bridge.speechModeSummary
                                    color: text
                                    wrapMode: Text.WordWrap
                                    font.pixelSize: 11
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 72
                            radius: 18
                            color: "#0a1624"
                            border.color: edge
                            border.width: 1

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 6

                                Text {
                                    text: "SAFETY"
                                    color: tertiaryAccent
                                    font.pixelSize: 10
                                    font.bold: true
                                    font.family: "Consolas"
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: responseEnvelopeModel.safety_flags && responseEnvelopeModel.safety_flags.length > 0 ? responseEnvelopeModel.safety_flags.join("\n") : "CLEAR"
                                    color: text
                                    wrapMode: Text.WordWrap
                                    font.pixelSize: 11
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 102
                            radius: 18
                            color: "#0a1624"
                            border.color: edge
                            border.width: 1

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 6

                                Text {
                                    text: "WHY THIS MODEL"
                                    color: tertiaryAccent
                                    font.pixelSize: 10
                                    font.bold: true
                                    font.family: "Consolas"
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: cockpitSummaryModel.model_rationale && cockpitSummaryModel.model_rationale.summary ? cockpitSummaryModel.model_rationale.summary : "Jarvis will explain model selection after the next routed turn."
                                    color: text
                                    wrapMode: Text.WordWrap
                                    maximumLineCount: 5
                                    elide: Text.ElideRight
                                    font.pixelSize: 11
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 72
                            radius: 18
                            color: "#0a1624"
                            border.color: edge
                            border.width: 1

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 6

                                Text {
                                    text: "TOOL CALLS"
                                    color: tertiaryAccent
                                    font.pixelSize: 10
                                    font.bold: true
                                    font.family: "Consolas"
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: responseEnvelopeModel.tool_calls && responseEnvelopeModel.tool_calls.length > 0 ? responseEnvelopeModel.tool_calls.map(function(item) { return item.name + " // " + item.status }).join("\n") : "0 calls"
                                    color: text
                                    wrapMode: Text.WordWrap
                                    font.pixelSize: 11
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 72
                            radius: 18
                            color: "#0a1624"
                            border.color: edge
                            border.width: 1

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 6

                                Text {
                                    text: "MEMORY USED"
                                    color: tertiaryAccent
                                    font.pixelSize: 10
                                    font.bold: true
                                    font.family: "Consolas"
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: cockpitSummaryModel.learning && cockpitSummaryModel.learning.intents && cockpitSummaryModel.learning.intents.length > 0 ? cockpitSummaryModel.learning.intents.join("\n") : (responseEnvelopeModel.memory_hits && responseEnvelopeModel.memory_hits.length > 0 ? responseEnvelopeModel.memory_hits.join("\n") : "0 recalls")
                                    color: text
                                    wrapMode: Text.WordWrap
                                    font.pixelSize: 11
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: responseEnvelopeModel.decision_path && responseEnvelopeModel.decision_path.length > 0 ? 100 : 72
                            radius: 18
                            color: "#0a1624"
                            border.color: edge
                            border.width: 1

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 6

                                Text {
                                    text: "DECISION PATH"
                                    color: tertiaryAccent
                                    font.pixelSize: 10
                                    font.bold: true
                                    font.family: "Consolas"
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: responseEnvelopeModel.decision_path && responseEnvelopeModel.decision_path.length > 0 ? responseEnvelopeModel.decision_path.join("\n") : compactText(responseEnvelopeModel.intent, "No route recorded")
                                    color: text
                                    wrapMode: Text.WordWrap
                                    maximumLineCount: 5
                                    elide: Text.ElideRight
                                    font.pixelSize: 11
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            radius: 18
                            color: "#0a1624"
                            border.color: edge
                            border.width: 1

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 6

                                Text {
                                    text: "WORKFLOW TRACE"
                                    color: accent
                                    font.pixelSize: 10
                                    font.bold: true
                                    font.family: "Consolas"
                                }

                                ListView {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    model: workflowTraceModel
                                    clip: true
                                    spacing: 8

                                    delegate: Rectangle {
                                        required property var modelData
                                        width: ListView.view.width
                                        height: traceColumn.implicitHeight + 12
                                        radius: 12
                                        color: Qt.rgba(11 / 255, 24 / 255, 40 / 255, 0.72)
                                        border.color: Qt.rgba(148 / 255, 204 / 255, 255 / 255, 0.08)
                                        border.width: 1

                                        Column {
                                            id: traceColumn
                                            anchors.fill: parent
                                            anchors.margins: 8
                                            spacing: 3

                                            Text {
                                                text: modelData.ts + "  " + modelData.step
                                                color: muted
                                                font.pixelSize: 9
                                                font.bold: true
                                                font.family: "Consolas"
                                            }

                                            Text {
                                                text: modelData.status.toUpperCase() + "  " + modelData.detail
                                                color: text
                                                wrapMode: Text.WordWrap
                                                font.pixelSize: 10
                                                width: parent.width
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    id: dock
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 24
                    width: 764
                    height: 92
                    radius: 28
                    color: Qt.rgba(7 / 255, 16 / 255, 27 / 255, 0.94)
                    border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.24)
                    border.width: 1

                    Row {
                        anchors.centerIn: parent
                        spacing: 10

                        Repeater {
                            model: [
                                { label: "MIC", caption: bridge.microphoneMuted ? "Muted" : "On", icon: bridge.microphoneMuted ? "m-" : "m+", action: "mic", active: !bridge.microphoneMuted, warning: bridge.microphoneMuted },
                                { label: "VOICE", caption: bridge.speakerMuted ? "Muted" : "Ready", icon: bridge.speakerMuted ? "s-" : "s+", action: "speaker", active: !bridge.speakerMuted, warning: bridge.speakerMuted },
                                { label: "PTT", caption: "Push", icon: "o", action: "ptt", active: bridge.assistantState === "listening" || bridge.assistantState === "transcribing", warning: false },
                                { label: "AUTO", caption: bridge.listenStatus === "AUTO LISTEN // ON" ? "Live" : "Off", icon: "a", action: "listen", active: bridge.listenStatus === "AUTO LISTEN // ON", warning: false },
                                { label: "STOP", caption: bridge.busy ? "Now" : "Idle", icon: "!", action: "interrupt", active: bridge.busy, warning: bridge.busy },
                                { label: "TEXT", caption: bridge.textFallbackVisible ? "Open" : "Shell", icon: ">", action: "text", active: bridge.textFallbackVisible, warning: false },
                                { label: "OPS", caption: bridge.operationsVisible ? "Open" : "Hidden", icon: "[]", action: "operations", active: bridge.operationsVisible, warning: approvalMode || debugMode || bridge.assistantState === "error" }
                            ]

                            delegate: Button {
                                id: actionButton
                                required property var modelData
                                width: 96
                                height: 64
                                text: modelData.icon
                                font.pixelSize: 13
                                font.bold: true
                                ToolTip.visible: hovered
                                ToolTip.delay: 200
                                ToolTip.text: modelData.label
                                background: Rectangle {
                                    radius: 20
                                    color: actionButton.down ? Qt.rgba(accent.r, accent.g, accent.b, 0.24) : modelData.active ? Qt.rgba(accent.r, accent.g, accent.b, 0.16) : Qt.rgba(11 / 255, 26 / 255, 43 / 255, 0.92)
                                    border.color: modelData.warning ? Qt.rgba(255 / 255, 141 / 255, 114 / 255, 0.40) : modelData.active ? Qt.rgba(accent.r, accent.g, accent.b, 0.34) : (actionButton.hovered ? Qt.rgba(accent.r, accent.g, accent.b, 0.26) : Qt.rgba(117 / 255, 190 / 255, 255 / 255, 0.14))
                                    border.width: 1
                                }
                                contentItem: Column {
                                    spacing: 1
                                    anchors.centerIn: parent

                                    Text {
                                        text: actionButton.text
                                        color: modelData.warning ? "#ffd1c5" : text
                                        horizontalAlignment: Text.AlignHCenter
                                        font.pixelSize: 13
                                        font.bold: true
                                        font.family: "Consolas"
                                        width: parent.width
                                    }

                                    Text {
                                        text: modelData.label
                                        color: text
                                        horizontalAlignment: Text.AlignHCenter
                                        font.pixelSize: 10
                                        font.bold: true
                                        font.family: "Consolas"
                                        width: parent.width
                                    }

                                    Text {
                                        text: modelData.caption
                                        color: muted
                                        horizontalAlignment: Text.AlignHCenter
                                        font.pixelSize: 9
                                        font.family: "Segoe UI"
                                        width: parent.width
                                    }
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
                                    else if (modelData.action === "operations") {
                                        if (bridge.operationsVisible)
                                            bridge.hideOperations()
                                        else
                                            bridge.openOperations()
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    visible: bridge.textFallbackVisible
                    width: terminalWidth
                    height: terminalHeight
                    radius: 22
                    color: Qt.rgba(9 / 255, 18 / 255, 31 / 255, 0.97)
                    border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.24)
                    border.width: 1
                    anchors.right: parent.right
                    anchors.rightMargin: 26
                    anchors.bottom: dock.top
                    anchors.bottomMargin: 18

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 10

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10

                            Button {
                                Layout.fillWidth: true
                                text: bridge.speechModeSummary.indexOf("ENGLISH") >= 0 ? "English Active" : "English"
                                onClicked: bridge.setSpeechLanguageMode("english")
                            }

                            Button {
                                Layout.fillWidth: true
                                text: bridge.speechModeSummary.indexOf("HINGLISH") >= 0 ? "Hinglish Active" : "Hinglish"
                                onClicked: bridge.setSpeechLanguageMode("hinglish")
                            }

                            Button {
                                Layout.fillWidth: true
                                text: bridge.speechModeSummary.indexOf("HINDI") >= 0 ? "Hindi Active" : "Hindi"
                                onClicked: bridge.setSpeechLanguageMode("hindi")
                            }
                        }

                        Text {
                            text: bridge.speechModeSummary
                            color: text
                            font.pixelSize: 12
                            wrapMode: Text.WordWrap

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

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2

                                Text {
                                    text: "LIVE COMMAND DECK"
                                    color: tertiaryAccent
                                    font.pixelSize: 10
                                    font.bold: true
                                    font.family: "Consolas"
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: bridge.ownerKnown ? ("Bound to " + bridge.ownerName + ". Camera and voice identity layers can build on this profile.") : "Bind the owner profile first, then use natural language commands like the terminal shell."
                                    color: muted
                                    wrapMode: Text.WordWrap
                                    maximumLineCount: 2
                                    elide: Text.ElideRight
                                    font.pixelSize: 11
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            radius: 16
                            color: "#08131f"
                            border.color: edge
                            border.width: 1

                            ScrollView {
                                anchors.fill: parent
                                anchors.margins: 10
                                clip: true

                                Text {
                                    width: parent.width
                                    text: bridge.conversationText
                                    color: text
                                    wrapMode: Text.Wrap
                                    font.pixelSize: 12
                                    font.family: "Consolas"
                                }
                            }
                        }

                        Flow {
                            Layout.fillWidth: true
                            spacing: 8

                            Repeater {
                                model: [
                                    { label: "Privacy", command: "privacy status" },
                                    { label: "Readiness", command: "learning readiness" },
                                    { label: "Model", command: "model status" },
                                    { label: "Start OMNIRA", command: "start omnira" },
                                    { label: "Owner", command: "my name is Vivek" },
                                    { label: "Alias", command: "when i say Viki, i mean Vivek" }
                                ]

                                delegate: Button {
                                    required property var modelData
                                    text: modelData.label
                                    enabled: !bridge.busy
                                    onClicked: {
                                        promptField.text = modelData.command
                                        promptField.forceActiveFocus()
                                        promptField.cursorPosition = promptField.text.length
                                    }
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10

                            TextField {
                                id: promptField
                                Layout.fillWidth: true
                                placeholderText: bridge.busy ? "Jarvis is responding..." : "Talk to Jarvis here"
                                placeholderTextColor: muted
                                enabled: !bridge.busy
                                color: text
                                selectedTextColor: glass
                                selectionColor: accent
                                font.pixelSize: 14
                                font.family: "Segoe UI"
                                leftPadding: 14
                                rightPadding: 14
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
                                width: 58
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
                }

                Rectangle {
                    visible: insightMode
                    width: 560
                    height: 290
                    radius: 24
                    color: Qt.rgba(9 / 255, 18 / 255, 31 / 255, 0.95)
                    border.color: Qt.rgba(accent.r, accent.g, accent.b, 0.18)
                    border.width: 1
                    anchors.left: parent.left
                    anchors.leftMargin: 26
                    anchors.bottom: dock.top
                    anchors.bottomMargin: 18

                    ScrollView {
                        anchors.fill: parent
                        anchors.margins: 14
                        clip: true

                        ColumnLayout {
                            width: parent.width
                            spacing: 10

                            Repeater {
                                model: visualOutputModel
                                delegate: Rectangle {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: insightBody.implicitHeight + 28
                                    radius: 18
                                    color: Qt.rgba(11 / 255, 24 / 255, 40 / 255, 0.82)
                                    border.color: modelData.kind === "command_result" ? Qt.rgba(accent.r, accent.g, accent.b, 0.26) : edge
                                    border.width: 1

                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 8

                                        Text {
                                            text: modelData.title
                                            color: tertiaryAccent
                                            font.pixelSize: 10
                                            font.bold: true
                                            font.family: "Consolas"
                                        }

                                        Loader {
                                            id: insightBody
                                            Layout.fillWidth: true
                                            sourceComponent: modelData.kind === "timeline" || modelData.kind === "workflow_trace" ? timelineCard : modelData.kind === "tree" || modelData.kind === "task_tree" || modelData.kind === "memory_used" ? treeCard : modelData.kind === "table" || modelData.kind === "comparison_table" ? tableCard : modelData.kind === "metrics" || modelData.kind === "status_cards" ? metricsCard : textCard
                                            onLoaded: item.payload = modelData
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    visible: settingsVisible
                    width: 360
                    height: 900
                    radius: 26
                    color: Qt.rgba(9 / 255, 18 / 255, 31 / 255, 0.96)
                    border.color: Qt.rgba(148 / 255, 204 / 255, 255 / 255, 0.18)
                    border.width: 1
                    anchors.horizontalCenter: parent.horizontalCenter
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

                        Text {
                            text: "Owner Profile"
                            color: muted
                            font.pixelSize: 10
                            font.bold: true
                            font.family: "Consolas"
                        }

                        TextField {
                            Layout.fillWidth: true
                            placeholderText: "Owner name"
                            placeholderTextColor: muted
                            text: bridge.ownerName
                            color: text
                            selectedTextColor: glass
                            selectionColor: accent
                            font.pixelSize: 13
                            font.family: "Segoe UI"
                            onAccepted: bridge.setOwnerName(text)
                            background: Rectangle {
                                color: "#0a1624"
                                radius: 14
                                border.color: edge
                                border.width: 1
                            }
                        }

                        Text {
                            text: "Presence And Learning"
                            color: muted
                            font.pixelSize: 10
                            font.bold: true
                            font.family: "Consolas"
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Switch {
                                checked: bridge.lowLatencyVoice
                                onToggled: bridge.setLowLatencyVoice(checked)
                            }

                            Text {
                                Layout.fillWidth: true
                                text: "Low-latency voice"
                                color: text
                                wrapMode: Text.WordWrap
                                font.pixelSize: 12
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Switch {
                                checked: bridge.cameraConsent
                                onToggled: bridge.setCameraConsent(checked)
                            }

                            Text {
                                Layout.fillWidth: true
                                text: "Camera consent for future owner verification"
                                color: text
                                wrapMode: Text.WordWrap
                                font.pixelSize: 12
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Switch {
                                checked: bridge.voiceLearningEnabled
                                onToggled: bridge.setVoiceLearningEnabled(checked)
                            }

                            Text {
                                Layout.fillWidth: true
                                text: "Voice learning preference"
                                color: text
                                wrapMode: Text.WordWrap
                                font.pixelSize: 12
                            }
                        }

                        Text {
                            text: "Learned Owner Profile"
                            color: muted
                            font.pixelSize: 10
                            font.bold: true
                            font.family: "Consolas"
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 132
                            radius: 16
                            color: "#0a1624"
                            border.color: edge
                            border.width: 1

                            ScrollView {
                                anchors.fill: parent
                                anchors.margins: 10
                                clip: true

                                Text {
                                    width: parent.width
                                    text: bridge.ownerProfileSummary
                                    color: text
                                    wrapMode: Text.WordWrap
                                    font.pixelSize: 12
                                }
                            }
                        }

                        Text {
                            text: "Response Style"
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
                                text: bridge.ownerResponseStyle === "concise" ? "Concise Active" : "Set Concise"
                                onClicked: bridge.setOwnerResponseStyle("concise")
                            }

                            Button {
                                Layout.fillWidth: true
                                text: bridge.ownerResponseStyle === "detailed" ? "Detailed Active" : "Set Detailed"
                                onClicked: bridge.setOwnerResponseStyle("detailed")
                            }
                        }

                        Text {
                            text: "Preferences"
                            color: muted
                            font.pixelSize: 10
                            font.bold: true
                            font.family: "Consolas"
                        }

                        TextArea {
                            id: ownerPreferencesArea
                            Layout.fillWidth: true
                            Layout.preferredHeight: 86
                            text: bridge.ownerPreferencesText
                            placeholderText: "One preference per line"
                            placeholderTextColor: muted
                            color: text
                            wrapMode: TextEdit.Wrap
                            selectByMouse: true
                            background: Rectangle {
                                color: "#0a1624"
                                radius: 14
                                border.color: edge
                                border.width: 1
                            }
                        }

                        Button {
                            Layout.fillWidth: true
                            text: "Save Preferences"
                            onClicked: bridge.saveOwnerPreferences(ownerPreferencesArea.text)
                        }

                        Text {
                            text: "Phrase Mappings"
                            color: muted
                            font.pixelSize: 10
                            font.bold: true
                            font.family: "Consolas"
                        }

                        TextArea {
                            id: ownerAliasesArea
                            Layout.fillWidth: true
                            Layout.preferredHeight: 86
                            text: bridge.ownerAliasesText
                            placeholderText: "spoken phrase = intended meaning"
                            placeholderTextColor: muted
                            color: text
                            wrapMode: TextEdit.Wrap
                            selectByMouse: true
                            background: Rectangle {
                                color: "#0a1624"
                                radius: 14
                                border.color: edge
                                border.width: 1
                            }
                        }

                        Button {
                            Layout.fillWidth: true
                            text: "Save Phrase Mappings"
                            onClicked: bridge.saveOwnerAliases(ownerAliasesArea.text)
                        }

                        Text {
                            text: "Adaptation Notes"
                            color: muted
                            font.pixelSize: 10
                            font.bold: true
                            font.family: "Consolas"
                        }

                        TextArea {
                            id: ownerNotesArea
                            Layout.fillWidth: true
                            Layout.preferredHeight: 86
                            text: bridge.ownerNotesText
                            placeholderText: "Speech, accent, workflow, or behavior notes"
                            placeholderTextColor: muted
                            color: text
                            wrapMode: TextEdit.Wrap
                            selectByMouse: true
                            background: Rectangle {
                                color: "#0a1624"
                                radius: 14
                                border.color: edge
                                border.width: 1
                            }
                        }

                        Button {
                            Layout.fillWidth: true
                            text: "Save Adaptation Notes"
                            onClicked: bridge.saveOwnerNotes(ownerNotesArea.text)
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

                        Text {
                            text: "Default UI Mode"
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
                                text: bridge.uiMode === "presence" ? "Presence Active" : "Presence"
                                onClicked: bridge.setDefaultUiMode("presence")
                            }

                            Button {
                                Layout.fillWidth: true
                                text: bridge.uiMode === "conversation" ? "Conversation Active" : "Conversation"
                                onClicked: bridge.setDefaultUiMode("conversation")
                            }

                            Button {
                                Layout.fillWidth: true
                                text: bridge.uiMode === "insight" ? "Insight Active" : "Insight"
                                onClicked: bridge.setDefaultUiMode("insight")
                            }
                        }

                        Text {
                            text: "Voice And Visibility"
                            color: muted
                            font.pixelSize: 10
                            font.bold: true
                            font.family: "Consolas"
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Switch {
                                checked: bridge.wakeWordEnabled
                                onToggled: bridge.setWakeWordEnabled(checked)
                            }

                            Text {
                                Layout.fillWidth: true
                                text: "Wake-word gate for live listen"
                                color: text
                                wrapMode: Text.WordWrap
                                font.pixelSize: 12
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Switch {
                                checked: bridge.showOperationsByDefault
                                onToggled: bridge.setShowOperationsByDefault(checked)
                            }

                            Text {
                                Layout.fillWidth: true
                                text: "Show operations panel on launch"
                                color: text
                                wrapMode: Text.WordWrap
                                font.pixelSize: 12
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Switch {
                                checked: bridge.debugModeEnabled
                                onToggled: {
                                    if (checked)
                                        bridge.enterDebugMode()
                                    else
                                        bridge.exitDebugMode()
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                text: "Enable debug mode"
                                color: text
                                wrapMode: Text.WordWrap
                                font.pixelSize: 12
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Switch {
                                checked: !bridge.microphoneMuted
                                onToggled: bridge.toggleMicrophoneMuted()
                            }

                            Text {
                                Layout.fillWidth: true
                                text: "Microphone default is restored from the current mute state"
                                color: text
                                wrapMode: Text.WordWrap
                                font.pixelSize: 12
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Switch {
                                checked: !bridge.speakerMuted
                                onToggled: bridge.toggleSpeakerMuted()
                            }

                            Text {
                                Layout.fillWidth: true
                                text: "Speaker default is restored from the current mute state"
                                color: text
                                wrapMode: Text.WordWrap
                                font.pixelSize: 12
                            }
                        }

                        Text {
                            text: "OMNIRA Endpoint"
                            color: muted
                            font.pixelSize: 10
                            font.bold: true
                            font.family: "Consolas"
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 56
                            radius: 14
                            color: "#0a1624"
                            border.color: edge
                            border.width: 1

                            Text {
                                anchors.fill: parent
                                anchors.margins: 12
                                text: bridge.omniraEndpoint.length > 0 ? bridge.omniraEndpoint : "No endpoint configured in config.yaml"
                                color: text
                                wrapMode: Text.WordWrap
                                verticalAlignment: Text.AlignVCenter
                                font.pixelSize: 12
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
                            text: "Manual start keeps Jarvis in the movable corner orb until invoked. Auto listen start engages live microphone mode when the shell boots. Camera consent and voice learning are stored locally for the future owner-recognition layer."
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

        Rectangle {
            property var payload
            radius: 14
            color: Qt.rgba(13 / 255, 29 / 255, 48 / 255, 0.88)
            border.color: Qt.rgba(148 / 255, 204 / 255, 255 / 255, 0.10)
            border.width: 1
            implicitHeight: bodyText.implicitHeight + 20

            Text {
                id: bodyText
                anchors.fill: parent
                anchors.margins: 10
                text: payload ? payload.body : ""
                color: text
                wrapMode: Text.WordWrap
                font.pixelSize: 12
                lineHeight: 1.15
            }
        }
    }

    Component {
        id: timelineCard

        Column {
            property var payload
            spacing: 6

            Repeater {
                model: payload ? payload.items : []
                delegate: Rectangle {
                    required property string modelData
                    width: parent.width
                    radius: 10
                    color: Qt.rgba(14 / 255, 31 / 255, 51 / 255, 0.78)
                    border.color: Qt.rgba(148 / 255, 204 / 255, 255 / 255, 0.08)
                    border.width: 1
                    implicitHeight: itemText.implicitHeight + 14

                    Text {
                        id: itemText
                        anchors.fill: parent
                        anchors.margins: 8
                        text: modelData
                        color: text
                        wrapMode: Text.WordWrap
                        font.pixelSize: 10
                    }
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
                delegate: Rectangle {
                    required property string modelData
                    width: parent.width
                    radius: 10
                    color: Qt.rgba(14 / 255, 31 / 255, 51 / 255, 0.70)
                    border.color: Qt.rgba(148 / 255, 204 / 255, 255 / 255, 0.08)
                    border.width: 1
                    implicitHeight: itemText.implicitHeight + 14

                    Text {
                        id: itemText
                        anchors.fill: parent
                        anchors.margins: 8
                        text: modelData
                        color: text
                        wrapMode: Text.WordWrap
                        font.pixelSize: 10
                    }
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
                delegate: Rectangle {
                    required property var modelData
                    width: parent.width
                    radius: 10
                    color: Qt.rgba(14 / 255, 31 / 255, 51 / 255, 0.72)
                    border.color: Qt.rgba(148 / 255, 204 / 255, 255 / 255, 0.08)
                    border.width: 1
                    implicitHeight: rowContent.implicitHeight + 14

                    RowLayout {
                        id: rowContent
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 10

                        Text {
                            text: modelData[0]
                            color: muted
                            font.pixelSize: 9
                            font.bold: true
                            font.family: "Consolas"
                            Layout.preferredWidth: 90
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
    }

    Component {
        id: metricsCard

        GridLayout {
            property var payload
            columns: 3
            columnSpacing: 10
            rowSpacing: 8

            Repeater {
                model: payload ? payload.metrics : []
                delegate: Rectangle {
                    required property var modelData
                    radius: 12
                    color: Qt.rgba(14 / 255, 31 / 255, 51 / 255, 0.78)
                    border.color: modelData.label === "Risk" ? riskColor(String(modelData.value).toLowerCase()) : Qt.rgba(148 / 255, 204 / 255, 255 / 255, 0.08)
                    border.width: 1
                    Layout.fillWidth: true
                    implicitHeight: metricColumn.implicitHeight + 18

                    Column {
                        id: metricColumn
                        anchors.fill: parent
                        anchors.margins: 9
                        spacing: 3

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
                            font.pixelSize: 11
                            wrapMode: Text.WordWrap
                            font.bold: true
                        }
                    }
                }
            }
        }
    }
}

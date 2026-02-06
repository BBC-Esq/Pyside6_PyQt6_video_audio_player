import os
import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QApplication, QSlider,
    QPushButton, QFileDialog, QHBoxLayout, QFrame, QLabel, QMessageBox,
    QStyle, QStyleOptionSlider
)
from PySide6.QtGui import QAction, QPalette, QColor, QShortcut, QKeySequence
from PySide6.QtCore import Qt, QTimer, QEvent, Signal, QObject
import vlc

if os.name == 'nt':
    import pythoncom
    pythoncom.CoInitialize()


class VLCEventHandler(QObject):
    end_reached = Signal()
    error_occurred = Signal()


class ClickableSlider(QSlider):
    seekRequested = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            groove_rect = self.style().subControlRect(
                QStyle.ComplexControl.CC_Slider, opt,
                QStyle.SubControl.SC_SliderGroove, self
            )
            if self.orientation() == Qt.Orientation.Horizontal:
                pos = int(event.position().x())
                value = QStyle.sliderValueFromPosition(
                    self.minimum(), self.maximum(),
                    pos - groove_rect.x(), groove_rect.width(),
                    opt.upsideDown
                )
            else:
                pos = int(event.position().y())
                value = QStyle.sliderValueFromPosition(
                    self.minimum(), self.maximum(),
                    pos - groove_rect.y(), groove_rect.height(),
                    opt.upsideDown
                )
            self.setValue(value)
            self.setSliderDown(True)
            self.sliderPressed.emit()
            self.seekRequested.emit()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.isSliderDown():
            self.setSliderDown(False)
            self.sliderReleased.emit()
        super().mouseReleaseEvent(event)


class MediaPlayer(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Media Player")
        self.setAcceptDrops(True)

        self.instance = None
        self.mediaplayer = None
        self.media = None
        self.is_paused = False
        self.is_dragging = False
        self.is_muted = False
        self.previous_volume = 50
        self.media_event_attached = False

        try:
            self.instance = vlc.Instance('--quiet')
            self.mediaplayer = self.instance.media_player_new()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize VLC: {str(e)}")

        self.vlc_events = VLCEventHandler()
        self.vlc_events.end_reached.connect(self.on_end_reached)
        self.vlc_events.error_occurred.connect(self.on_error)

        self.attach_player_events()
        self.create_ui()
        self.setup_shortcuts()

    def attach_player_events(self):
        em = self.mediaplayer.event_manager()
        em.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_vlc_end_reached)
        em.event_attach(vlc.EventType.MediaPlayerEncounteredError, self._on_vlc_error)

    def detach_player_events(self):
        try:
            em = self.mediaplayer.event_manager()
            em.event_detach(vlc.EventType.MediaPlayerEndReached, self._on_vlc_end_reached)
            em.event_detach(vlc.EventType.MediaPlayerEncounteredError, self._on_vlc_error)
        except Exception:
            pass

    def _on_vlc_end_reached(self, event):
        self.vlc_events.end_reached.emit()

    def _on_vlc_error(self, event):
        self.vlc_events.error_occurred.emit()

    def on_end_reached(self):
        self.stop()

    def on_error(self):
        self.stop()
        QMessageBox.warning(self, "Playback Error", "An error occurred during playback.")

    def create_ui(self):
        self.widget = QWidget(self)
        self.setCentralWidget(self.widget)

        self.videoframe = QFrame()
        self.videoframe.setMinimumSize(320, 240)
        self.videoframe.installEventFilter(self)

        self.palette = self.videoframe.palette()
        self.palette.setColor(QPalette.Window, QColor(0, 0, 0))
        self.videoframe.setPalette(self.palette)
        self.videoframe.setAutoFillBackground(True)

        self.overlay = QWidget(self.videoframe)
        self.overlay.setStyleSheet("background: transparent;")
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.overlay.setMouseTracking(True)
        self.overlay.installEventFilter(self)

        self.positionslider = ClickableSlider(Qt.Orientation.Horizontal, self)
        self.positionslider.setToolTip("Position")
        self.positionslider.setMaximum(1000)
        self.positionslider.seekRequested.connect(self.set_position)
        self.positionslider.sliderPressed.connect(self.slider_pressed)
        self.positionslider.sliderReleased.connect(self.slider_released)

        self.timelabel = QLabel("00:00 / 00:00")
        self.timelabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hbuttonbox = QHBoxLayout()

        self.playbutton = QPushButton("Play")
        hbuttonbox.addWidget(self.playbutton)
        self.playbutton.clicked.connect(self.play_pause)

        self.stopbutton = QPushButton("Stop")
        hbuttonbox.addWidget(self.stopbutton)
        self.stopbutton.clicked.connect(self.stop)

        hbuttonbox.addStretch(1)

        self.mutebutton = QPushButton("\U0001F50A")
        self.mutebutton.setFixedWidth(40)
        self.mutebutton.clicked.connect(self.toggle_mute)
        hbuttonbox.addWidget(self.mutebutton)

        self.volumeslider = QSlider(Qt.Orientation.Horizontal, self)
        self.volumeslider.setMaximum(100)
        self.volumeslider.setFixedWidth(100)

        initial_volume = self.mediaplayer.audio_get_volume()
        if initial_volume == -1 or initial_volume < 0:
            initial_volume = 50
            self.mediaplayer.audio_set_volume(initial_volume)
        self.volumeslider.setValue(initial_volume)
        self.previous_volume = initial_volume

        self.volumeslider.setToolTip("Volume")
        hbuttonbox.addWidget(self.volumeslider)
        self.volumeslider.valueChanged.connect(self.set_volume)

        self.volumelabel = QLabel(f"{initial_volume}%")
        self.volumelabel.setFixedWidth(45)
        self.volumelabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hbuttonbox.addWidget(self.volumelabel)

        self.control_bar = QWidget()
        self.control_bar.setMouseTracking(True)
        self.control_bar.installEventFilter(self)
        control_bar_layout = QVBoxLayout(self.control_bar)
        control_bar_layout.setContentsMargins(0, 0, 0, 0)
        control_bar_layout.setSpacing(5)
        control_bar_layout.addWidget(self.positionslider)
        control_bar_layout.addWidget(self.timelabel)
        control_bar_layout.addLayout(hbuttonbox)

        self.vboxlayout = QVBoxLayout()
        self.vboxlayout.addWidget(self.videoframe, 1)
        self.vboxlayout.addWidget(self.control_bar)

        self.widget.setLayout(self.vboxlayout)

        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")

        open_action = QAction("Load Video", self)
        close_action = QAction("Close App", self)
        file_menu.addAction(open_action)
        file_menu.addAction(close_action)

        open_action.triggered.connect(self.open_file)
        close_action.triggered.connect(self.close)

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_ui)

        self.hide_timer = QTimer(self)
        self.hide_timer.setInterval(3000)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_controls)

        self.setMinimumSize(400, 350)

    def setup_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self.play_pause)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, lambda: self.skip(-5000))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, lambda: self.skip(5000))
        QShortcut(QKeySequence(Qt.Key.Key_Up), self, lambda: self.adjust_volume(10))
        QShortcut(QKeySequence(Qt.Key.Key_Down), self, lambda: self.adjust_volume(-10))
        QShortcut(QKeySequence(Qt.Key.Key_M), self, self.toggle_mute)
        QShortcut(QKeySequence(Qt.Key.Key_F11), self, self.toggle_fullscreen)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.exit_fullscreen)
        QShortcut(QKeySequence(Qt.Key.Key_F), self, self.toggle_fullscreen)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'overlay'):
            self.overlay.setGeometry(self.videoframe.rect())

    def eventFilter(self, obj, event):
        if obj == self.videoframe:
            if event.type() == QEvent.Type.Resize:
                self.overlay.setGeometry(self.videoframe.rect())
                return False
        elif obj == self.overlay:
            if event.type() == QEvent.Type.MouseButtonDblClick:
                self.toggle_fullscreen()
                return True
            elif event.type() == QEvent.Type.MouseMove and self.isFullScreen():
                self.show_controls()
                return False
        elif obj == self.control_bar and event.type() == QEvent.Type.MouseMove:
            if self.isFullScreen():
                self.hide_timer.start()
            return False
        return super().eventFilter(obj, event)

    def show_controls(self):
        if self.isFullScreen():
            self.control_bar.show()
            self.hide_timer.start()

    def hide_controls(self):
        if self.isFullScreen():
            self.control_bar.hide()

    def play_pause(self):
        if self.mediaplayer.is_playing():
            self.mediaplayer.pause()
            self.playbutton.setText("Play")
            self.is_paused = True
            self.timer.stop()
        else:
            if self.mediaplayer.play() == -1:
                self.open_file()
                return
            self.playbutton.setText("Pause")
            self.timer.start()
            self.is_paused = False

    def stop(self):
        self.mediaplayer.stop()
        self.playbutton.setText("Play")
        self.is_paused = False
        self.timer.stop()
        self.positionslider.setValue(0)
        self.timelabel.setText("00:00 / 00:00")

    def open_file(self):
        dialog_txt = "Choose Media File"
        filename, _ = QFileDialog.getOpenFileName(self, dialog_txt, os.path.expanduser('~'))
        if not filename:
            return
        self.load_file(filename)

    def detach_media_events(self):
        if self.media and self.media_event_attached:
            try:
                em = self.media.event_manager()
                em.event_detach(vlc.EventType.MediaParsedChanged, self.on_media_parsed)
            except Exception:
                pass
            self.media_event_attached = False

    def load_file(self, filename):
        try:
            self.mediaplayer.stop()

            self.detach_media_events()
            if self.media:
                self.media.release()
                self.media = None

            self.media = self.instance.media_new(filename)
            self.mediaplayer.set_media(self.media)

            self.setWindowTitle(os.path.basename(filename))

            event_manager = self.media.event_manager()
            event_manager.event_attach(vlc.EventType.MediaParsedChanged, self.on_media_parsed)
            self.media_event_attached = True

            self.media.parse_with_options(vlc.MediaParseFlag.local, 0)

            if sys.platform == "darwin":
                self.mediaplayer.set_nsobject(int(self.videoframe.winId()))
            elif sys.platform.startswith("linux"):
                self.mediaplayer.set_xwindow(int(self.videoframe.winId()))
            else:
                self.mediaplayer.set_hwnd(int(self.videoframe.winId()))

            self.mediaplayer.video_set_mouse_input(False)
            self.mediaplayer.video_set_key_input(False)

            self.is_paused = False
            self.mediaplayer.play()
            self.playbutton.setText("Pause")
            self.timer.start()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load media file: {str(e)}")

    def on_media_parsed(self, event):
        media = self.media
        if media:
            try:
                title = media.get_meta(vlc.Meta.Title)
            except Exception:
                return
            if title:
                QTimer.singleShot(0, lambda t=title: self.setWindowTitle(t))

    def set_volume(self, volume):
        self.mediaplayer.audio_set_volume(volume)
        self.volumelabel.setText(f"{volume}%")
        self.mutebutton.setText("\U0001F507" if volume == 0 else "\U0001F50A")

    def adjust_volume(self, delta):
        current = self.volumeslider.value()
        new_volume = max(0, min(100, current + delta))
        self.volumeslider.setValue(new_volume)

    def toggle_mute(self):
        if self.is_muted:
            self.volumeslider.setValue(self.previous_volume)
            self.is_muted = False
        else:
            current = self.volumeslider.value()
            if current > 0:
                self.previous_volume = current
            self.volumeslider.setValue(0)
            self.is_muted = True

    def skip(self, milliseconds):
        if self.media:
            current_time = self.mediaplayer.get_time()
            total_time = self.mediaplayer.get_length()
            new_time = max(0, min(total_time, current_time + milliseconds))
            self.mediaplayer.set_time(int(new_time))

    def slider_pressed(self):
        self.is_dragging = True

    def slider_released(self):
        if self.is_dragging:
            self.is_dragging = False
            self.set_position()

    def set_position(self):
        pos = self.positionslider.value()
        self.mediaplayer.set_position(pos / 1000.0)

    def update_ui(self):
        if not self.is_dragging:
            media_pos = int(self.mediaplayer.get_position() * 1000)
            self.positionslider.setValue(media_pos)

        current_time = self.mediaplayer.get_time()
        total_time = self.mediaplayer.get_length()

        if current_time >= 0 and total_time > 0:
            current_str = self.format_time(current_time)
            total_str = self.format_time(total_time)
            self.timelabel.setText(f"{current_str} / {total_str}")

    def format_time(self, milliseconds):
        seconds = milliseconds // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        hours = minutes // 60
        minutes = minutes % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def enter_fullscreen(self):
        self.menuBar().hide()
        self.widget.layout().setContentsMargins(0, 0, 0, 0)
        self.showFullScreen()
        self.hide_timer.start()

    def exit_fullscreen(self):
        self.hide_timer.stop()
        self.menuBar().show()
        self.control_bar.show()
        self.widget.layout().setContentsMargins(9, 9, 9, 9)
        self.showNormal()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self.load_file(urls[0].toLocalFile())

    def closeEvent(self, event):
        try:
            self.hide_timer.stop()
            self.timer.stop()
            self.detach_player_events()
            if self.mediaplayer:
                self.mediaplayer.stop()
            self.detach_media_events()
            if self.media:
                self.media.release()
            if self.mediaplayer:
                self.mediaplayer.release()
            if self.instance:
                self.instance.release()
        except Exception:
            pass
        event.accept()


def main():
    app = QApplication(sys.argv)

    app.setStyle("Fusion")
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    app.setPalette(dark_palette)

    try:
        player = MediaPlayer()
    except RuntimeError as e:
        QMessageBox.critical(None, "Error", str(e))
        sys.exit(1)

    player.show()
    player.resize(640, 480)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
import os
import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QApplication, QSlider, 
    QPushButton, QFileDialog, QHBoxLayout, QFrame, QLabel, QMessageBox
)
from PySide6.QtGui import QAction, QPalette, QColor, QShortcut, QKeySequence
from PySide6.QtCore import Qt, QTimer, QEvent
import vlc

if os.name == 'nt':
    import pythoncom
    pythoncom.CoInitialize()


class ClickableSlider(QSlider):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            value = QSlider.minimum(self) + ((QSlider.maximum(self) - QSlider.minimum(self)) * event.position().x()) / self.width()
            self.setValue(int(value))
            self.sliderPressed.emit()
            self.sliderMoved.emit(int(value))
            self.sliderReleased.emit()
        super().mousePressEvent(event)


class MediaPlayer(QMainWindow):

    def __init__(self, master=None):
        super().__init__(master)
        self.setWindowTitle("Media Player")
        self.setAcceptDrops(True)

        try:
            self.instance = vlc.Instance('--quiet')
            self.mediaplayer = self.instance.media_player_new()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to initialize VLC: {str(e)}")
            sys.exit(1)

        self.media = None
        self.is_paused = False
        self.is_dragging = False
        self.is_muted = False
        self.previous_volume = 50
        
        self.create_ui()
        self.setup_shortcuts()

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

        self.positionslider = ClickableSlider(Qt.Orientation.Horizontal, self)
        self.positionslider.setToolTip("Position")
        self.positionslider.setMaximum(1000)
        self.positionslider.sliderMoved.connect(self.set_position)
        self.positionslider.sliderPressed.connect(self.slider_pressed)
        self.positionslider.sliderReleased.connect(self.slider_released)

        self.timelabel = QLabel("00:00 / 00:00")
        self.timelabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.hbuttonbox = QHBoxLayout()
        
        self.playbutton = QPushButton("Play")
        self.hbuttonbox.addWidget(self.playbutton)
        self.playbutton.clicked.connect(self.play_pause)

        self.stopbutton = QPushButton("Stop")
        self.hbuttonbox.addWidget(self.stopbutton)
        self.stopbutton.clicked.connect(self.stop)

        self.hbuttonbox.addStretch(1)
        
        self.mutebutton = QPushButton("🔊")
        self.mutebutton.setFixedWidth(40)
        self.mutebutton.clicked.connect(self.toggle_mute)
        self.hbuttonbox.addWidget(self.mutebutton)
        
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
        self.hbuttonbox.addWidget(self.volumeslider)
        self.volumeslider.valueChanged.connect(self.set_volume)
        
        self.volumelabel = QLabel(f"{initial_volume}%")
        self.volumelabel.setFixedWidth(45)
        self.volumelabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hbuttonbox.addWidget(self.volumelabel)

        self.vboxlayout = QVBoxLayout()
        self.vboxlayout.addWidget(self.videoframe, 1)
        self.vboxlayout.addWidget(self.positionslider)
        self.vboxlayout.addWidget(self.timelabel)
        self.vboxlayout.addLayout(self.hbuttonbox)

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

    def eventFilter(self, obj, event):
        if obj == self.videoframe and event.type() == QEvent.Type.MouseButtonDblClick:
            self.toggle_fullscreen()
            return True
        return super().eventFilter(obj, event)

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
        self.timer.stop()
        self.positionslider.setValue(0)
        self.timelabel.setText("00:00 / 00:00")

    def open_file(self):
        dialog_txt = "Choose Media File"
        filename, _ = QFileDialog.getOpenFileName(self, dialog_txt, os.path.expanduser('~'))
        if not filename:
            return
        self.load_file(filename)

    def load_file(self, filename):
        try:
            self.media = self.instance.media_new(filename)
            self.mediaplayer.set_media(self.media)

            self.media.parse_with_options(vlc.MediaParseFlag.local, 0)

            self.setWindowTitle(os.path.basename(filename))
            
            event_manager = self.media.event_manager()
            event_manager.event_attach(vlc.EventType.MediaParsedChanged, self.on_media_parsed)

            if sys.platform == "darwin":
                self.mediaplayer.set_nsobject(int(self.videoframe.winId()))
            elif sys.platform.startswith("linux"):
                self.mediaplayer.set_xwindow(int(self.videoframe.winId()))
            else:
                self.mediaplayer.set_hwnd(int(self.videoframe.winId()))

            self.mediaplayer.video_set_mouse_input(False)
            self.mediaplayer.video_set_key_input(False)

            self.play_pause()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load media file: {str(e)}")

    def on_media_parsed(self, event):
        if self.media:
            title = self.media.get_meta(vlc.Meta.Title)
            if title:
                QTimer.singleShot(0, lambda: self.setWindowTitle(title))

    def set_volume(self, volume):
        self.mediaplayer.audio_set_volume(volume)
        self.volumelabel.setText(f"{volume}%")
        if volume == 0:
            self.mutebutton.setText("🔇")
            self.is_muted = True
        else:
            self.mutebutton.setText("🔊")
            self.is_muted = False
            self.previous_volume = volume

    def adjust_volume(self, delta):
        current = self.volumeslider.value()
        new_volume = max(0, min(100, current + delta))
        self.volumeslider.setValue(new_volume)

    def toggle_mute(self):
        if self.is_muted:
            self.volumeslider.setValue(self.previous_volume)
            self.mutebutton.setText("🔊")
            self.is_muted = False
        else:
            self.previous_volume = self.volumeslider.value()
            self.volumeslider.setValue(0)
            self.mutebutton.setText("🔇")
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

        if not self.mediaplayer.is_playing():
            self.timer.stop()
            if not self.is_paused:
                self.stop()

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

    def toggle_fullscreen(self, event=None):
        if self.isFullScreen():
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def enter_fullscreen(self):
        self.menuBar().hide()
        self.positionslider.hide()
        self.timelabel.hide()
        self.widget.layout().setContentsMargins(0, 0, 0, 0)
        
        for i in range(self.hbuttonbox.count()):
            widget = self.hbuttonbox.itemAt(i).widget()
            if widget:
                widget.hide()
        
        self.showFullScreen()

    def exit_fullscreen(self):
        self.menuBar().show()
        self.positionslider.show()
        self.timelabel.show()
        self.widget.layout().setContentsMargins(9, 9, 9, 9)
        
        for i in range(self.hbuttonbox.count()):
            widget = self.hbuttonbox.itemAt(i).widget()
            if widget:
                widget.show()
        
        self.showNormal()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self.load_file(urls[0].toLocalFile())

    def closeEvent(self, event):
        self.timer.stop()
        self.mediaplayer.stop()
        if self.media:
            self.media.release()
        self.mediaplayer.release()
        self.instance.release()
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
    
    player = MediaPlayer()
    player.show()
    player.resize(640, 480)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
import os
import sys

from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QApplication, QSlider, QPushButton, QFileDialog, QHBoxLayout, QFrame, QLabel, QMessageBox
from PyQt6.QtGui import QAction, QPalette, QColor
from PyQt6.QtCore import Qt, QTimer
import vlc

if os.name == 'nt':
    import pythoncom
    pythoncom.CoInitialize()

class MediaPlayer(QMainWindow):

    def __init__(self, master=None):
        super().__init__(master)
        self.setWindowTitle("Media Player")

        try:
            self.instance = vlc.Instance('--quiet')
            self.mediaplayer = self.instance.media_player_new()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to initialize VLC: {str(e)}")
            sys.exit(1)

        self.media = None
        self.create_ui()
        self.is_paused = False
        self.is_dragging = False

    def create_ui(self):
        self.widget = QWidget(self)
        self.setCentralWidget(self.widget)

        self.videoframe = QFrame()

        self.palette = self.videoframe.palette()
        self.palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0))
        self.videoframe.setPalette(self.palette)
        self.videoframe.setAutoFillBackground(True)

        self.positionslider = QSlider(Qt.Orientation.Horizontal, self)
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
        self.volumeslider = QSlider(Qt.Orientation.Horizontal, self)
        self.volumeslider.setMaximum(100)
        
        initial_volume = self.mediaplayer.audio_get_volume()
        if initial_volume == -1 or initial_volume < 0:
            initial_volume = 50
            self.mediaplayer.audio_set_volume(initial_volume)
        self.volumeslider.setValue(initial_volume)
        
        self.volumeslider.setToolTip("Volume")
        self.hbuttonbox.addWidget(self.volumeslider)
        self.volumeslider.valueChanged.connect(self.set_volume)

        self.vboxlayout = QVBoxLayout()
        self.vboxlayout.addWidget(self.videoframe)
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
            self.mediaplayer.play()
            self.playbutton.setText("Pause")
            self.timer.start()
            self.is_paused = False

    def stop(self):
        self.mediaplayer.stop()
        self.playbutton.setText("Play")
        self.timer.stop()

    def open_file(self):
        dialog_txt = "Choose Media File"
        filename, _ = QFileDialog.getOpenFileName(self, dialog_txt, os.path.expanduser('~'))
        if not filename:
            return

        try:
            self.media = self.instance.media_new(filename)
            self.mediaplayer.set_media(self.media)

            self.media.parse_with_options(vlc.MediaParseFlag.local, 5000)

            title = self.media.get_meta(vlc.Meta.Title)
            if title:
                self.setWindowTitle(title)
            else:
                self.setWindowTitle(os.path.basename(filename))

            if sys.platform == "darwin":
                self.mediaplayer.set_nsobject(int(self.videoframe.winId()))
            elif sys.platform.startswith("linux"):
                self.mediaplayer.set_xwindow(int(self.videoframe.winId()))
            else:
                self.mediaplayer.set_hwnd(int(self.videoframe.winId()))

            self.play_pause()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load media file: {str(e)}")

    def set_volume(self, volume):
        self.mediaplayer.audio_set_volume(volume)

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
    player = MediaPlayer()
    player.show()
    player.resize(640, 480)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
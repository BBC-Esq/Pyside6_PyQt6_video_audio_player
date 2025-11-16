import os
import sys

from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QApplication, QSlider, QPushButton, QFileDialog, QHBoxLayout, QFrame
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

        self.instance = vlc.Instance('--quiet')

        self.media = None

        self.mediaplayer = self.instance.media_player_new()

        self.create_ui()
        self.is_paused = False

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
        self.positionslider.sliderPressed.connect(self.set_position)

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
        self.volumeslider.setValue(self.mediaplayer.audio_get_volume())
        self.volumeslider.setToolTip("Volume")
        self.hbuttonbox.addWidget(self.volumeslider)
        self.volumeslider.valueChanged.connect(self.set_volume)

        self.vboxlayout = QVBoxLayout()
        self.vboxlayout.addWidget(self.videoframe)
        self.vboxlayout.addWidget(self.positionslider)
        self.vboxlayout.addLayout(self.hbuttonbox)

        self.widget.setLayout(self.vboxlayout)

        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")

        open_action = QAction("Load Video", self)
        close_action = QAction("Close App", self)
        file_menu.addAction(open_action)
        file_menu.addAction(close_action)

        open_action.triggered.connect(self.open_file)
        close_action.triggered.connect(sys.exit)

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

    def open_file(self):
        dialog_txt = "Choose Media File"
        filename, _ = QFileDialog.getOpenFileName(self, dialog_txt, os.path.expanduser('~'))
        if not filename:
            return

        self.media = self.instance.media_new(filename)
        self.mediaplayer.set_media(self.media)

        self.media.parse()

        self.setWindowTitle(self.media.get_meta(vlc.Meta.Title))

        self.mediaplayer.set_hwnd(int(self.videoframe.winId()))

        self.play_pause()

    def set_volume(self, volume):
        self.mediaplayer.audio_set_volume(volume)

    def set_position(self):
        self.timer.stop()
        pos = self.positionslider.value()
        self.mediaplayer.set_position(pos / 1000.0)
        self.timer.start()

    def update_ui(self):
        media_pos = int(self.mediaplayer.get_position() * 1000)
        self.positionslider.setValue(media_pos)

        if not self.mediaplayer.is_playing():
            self.timer.stop()
            if not self.is_paused:
                self.stop()

def main():
    app = QApplication(sys.argv)
    player = MediaPlayer()
    player.show()
    player.resize(640, 480)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
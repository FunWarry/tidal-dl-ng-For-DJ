################################################################################
## Form generated from reading UI file 'dialog_playlist_manager.ui'
##
## Created by: Qt User Interface Compiler version 6.10.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import QCoreApplication, QMetaObject, QRect, QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)


class Ui_DialogPlaylistManager:
    def setupUi(self, DialogPlaylistManager):
        if not DialogPlaylistManager.objectName():
            DialogPlaylistManager.setObjectName("DialogPlaylistManager")
        DialogPlaylistManager.resize(609, 760)
        DialogPlaylistManager.setMinimumSize(QSize(520, 560))
        self.verticalLayoutRoot = QVBoxLayout(DialogPlaylistManager)
        self.verticalLayoutRoot.setObjectName("verticalLayoutRoot")
        self.horizontalLayoutHeader = QHBoxLayout()
        self.horizontalLayoutHeader.setObjectName("horizontalLayoutHeader")
        self.labelTitle = QLabel(DialogPlaylistManager)
        self.labelTitle.setObjectName("labelTitle")
        self.labelTitle.setWordWrap(True)

        self.horizontalLayoutHeader.addWidget(self.labelTitle)

        self.verticalLayoutRoot.addLayout(self.horizontalLayoutHeader)

        self.frameSeparator = QFrame(DialogPlaylistManager)
        self.frameSeparator.setObjectName("frameSeparator")
        self.frameSeparator.setFrameShape(QFrame.Shape.HLine)
        self.frameSeparator.setFrameShadow(QFrame.Shadow.Sunken)

        self.verticalLayoutRoot.addWidget(self.frameSeparator)

        self.scrollArea = QScrollArea(DialogPlaylistManager)
        self.scrollArea.setObjectName("scrollArea")
        self.scrollArea.setWidgetResizable(True)
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setObjectName("scrollAreaWidgetContents")
        self.scrollAreaWidgetContents.setGeometry(QRect(0, 0, 589, 666))
        self.verticalLayoutList = QVBoxLayout(self.scrollAreaWidgetContents)
        self.verticalLayoutList.setObjectName("verticalLayoutList")
        self.labelEmpty = QLabel(self.scrollAreaWidgetContents)
        self.labelEmpty.setObjectName("labelEmpty")
        self.labelEmpty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.verticalLayoutList.addWidget(self.labelEmpty)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayoutList.addItem(self.verticalSpacer)

        self.scrollArea.setWidget(self.scrollAreaWidgetContents)

        self.verticalLayoutRoot.addWidget(self.scrollArea)

        self.frameFooterSeparator = QFrame(DialogPlaylistManager)
        self.frameFooterSeparator.setObjectName("frameFooterSeparator")
        self.frameFooterSeparator.setFrameShape(QFrame.Shape.HLine)
        self.frameFooterSeparator.setFrameShadow(QFrame.Shadow.Sunken)

        self.verticalLayoutRoot.addWidget(self.frameFooterSeparator)

        self.horizontalLayoutFooter = QHBoxLayout()
        self.horizontalLayoutFooter.setObjectName("horizontalLayoutFooter")
        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayoutFooter.addItem(self.horizontalSpacer)

        self.buttonClose = QPushButton(DialogPlaylistManager)
        self.buttonClose.setObjectName("buttonClose")

        self.horizontalLayoutFooter.addWidget(self.buttonClose)

        self.verticalLayoutRoot.addLayout(self.horizontalLayoutFooter)

        self.retranslateUi(DialogPlaylistManager)
        self.buttonClose.clicked.connect(DialogPlaylistManager.accept)

        self.buttonClose.setDefault(True)

        QMetaObject.connectSlotsByName(DialogPlaylistManager)

    # setupUi

    def retranslateUi(self, DialogPlaylistManager):
        DialogPlaylistManager.setWindowTitle(
            QCoreApplication.translate("DialogPlaylistManager", "G\u00e9rer les playlists", None)
        )
        self.labelTitle.setText(
            QCoreApplication.translate(
                "DialogPlaylistManager",
                'G\u00e9rer les playlists pour : <b><span style="color:#1e88e5;">Titre de la Piste</span></b>',
                None,
            )
        )
        self.labelEmpty.setText(
            QCoreApplication.translate("DialogPlaylistManager", "Aucune playlist disponible.", None)
        )
        self.buttonClose.setText(QCoreApplication.translate("DialogPlaylistManager", "Fermer", None))

    # retranslateUi

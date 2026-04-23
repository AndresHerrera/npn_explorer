# -*- coding: utf-8 -*-
"""Herramienta de mapa: identifica el valor de un atributo en la posición del cursor."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QCursor
from qgis.gui import QgsMapTool, QgsMapToolIdentify


class FeatureProbeMapTool(QgsMapTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self._layer = None
        self._field = None
        self._on_value = None
        self._on_double_click = None
        self._identify = QgsMapToolIdentify(canvas)

    def set_target(self, layer, field_name, on_value_callback, on_double_click=None):
        self._layer = layer
        self._field = field_name
        self._on_value = on_value_callback
        self._on_double_click = on_double_click

    def canvasMoveEvent(self, e):
        if not self._layer or not self._field or not self._on_value:
            return
        if not self._layer.isValid() or self._layer not in self.canvas().layers():
            self._on_value(None)
            return
        res = self._identify.identify(
            int(e.x()),
            int(e.y()),
            [self._layer],
            QgsMapToolIdentify.TopDownStopAtFirst,
        )
        if not res:
            self._on_value(None)
            return
        feat = res[0].mFeature
        idx = self._layer.fields().indexOf(self._field)
        if idx < 0:
            self._on_value(None)
            return
        self._on_value(feat.attribute(idx))

    def canvasDoubleClickEvent(self, e):
        if self._on_double_click is not None:
            self._on_double_click(e)
            e.accept()
        else:
            super().canvasDoubleClickEvent(e)

    def canvasLeaveEvent(self, e):
        if self._on_value:
            self._on_value(None)
        super().canvasLeaveEvent(e)

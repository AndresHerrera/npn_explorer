# -*- coding: utf-8 -*-
"""Panel y herramienta para leer un atributo bajo el cursor en una capa vectorial."""

import os

from qgis.PyQt.QtCore import Qt, QSize

try:
    from qgis.PyQt.QtCore import NULL
except ImportError:  # pragma: no cover
    NULL = None
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QApplication,
    QDockWidget,
    QFormLayout,
    QFrame,
    QLineEdit,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qgis.core import Qgis, QgsApplication, QgsMapLayerProxyModel
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox

from .feature_probe_map_tool import FeatureProbeMapTool
from .npn_analysis import (
    CAMPOS_NPN_ORDEN,
    MSG_NPN_VACIO_NULO,
    _normalize_value_text,
    analizar_npn,
)


def _plugin_dir():
    return os.path.dirname(__file__)


def _icon_copiar_portapapeles():
    """Icono típico de copiar (tema QGIS, :/images o icono de tema edit-copy)."""
    app = QgsApplication.instance()
    if app is not None:
        for name in ("/mActionEditCopy.svg", "mActionEditCopy.svg"):
            ico = app.getThemeIcon(name)
            if not ico.isNull():
                return ico
    for path in (
        ":/images/themes/default/mActionEditCopy.svg",
        ":/images/themes/default/mActionEditCopy.png",
    ):
        ico = QIcon(path)
        if not ico.isNull():
            return ico
    for theme_name in ("edit-copy", "gtk-edit-copy", "stock_edit-copy", "gtk-copy"):
        ico = QIcon.fromTheme(theme_name, QIcon())
        if not ico.isNull():
            return ico
    p = os.path.join(_plugin_dir(), "icons", "copy.svg")
    if os.path.exists(p):
        ico = QIcon(p)
        if not ico.isNull():
            return ico
    return QIcon()


class _ValueLineEdit(QLineEdit):
    """Campo de valor; doble clic fija o libera el valor mostrado."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self._p = plugin

    def mouseDoubleClickEvent(self, e):
        if self._p is not None and not getattr(self._p, "_unloaded", True):
            self._p._toggle_value_lock()
        super().mouseDoubleClickEvent(e)


class NpnExplorer:
    def __init__(self, iface):
        self.iface = iface
        self._dock = None
        self._tool = None
        self._action = None
        self._toolbar = None
        self._value_field = None
        self._layer_combo = None
        self._field_combo = None
        self._btn_probe = None
        self._unloaded = False
        # Misma ref en connect/disconnect (PyQt6 a veces falla con el método vinculado)
        self._map_tool_set_slot = None
        self._value_locked = False
        self._npn_error_label = None
        self._npn_value_labels = None  # dict nombre_campo -> QLabel
        self._npn_result_scroll = None
        self._btn_copy = None

    def initGui(self):
        self._unloaded = False
        self._value_locked = False
        self._tool = FeatureProbeMapTool(self.iface.mapCanvas())
        self._tool.set_target(None, None, self._on_probe_value, self._on_map_double_click)

        self._build_dock()
        self._toolbar, self._action = self._add_toolbar()

        self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._dock)
        self._dock.setVisible(True)
        c = self.iface.mapCanvas()

        def _map_tool_set_slot(*args, **_kwargs):
            if self._unloaded:
                return
            n = len(args)
            new_tool = args[0] if n else None
            old_tool = args[1] if n > 1 else None
            self._on_map_tool_set(new_tool, old_tool)

        self._map_tool_set_slot = _map_tool_set_slot
        c.mapToolSet.connect(self._map_tool_set_slot)

    def _icon(self):
        path = os.path.join(_plugin_dir(), "icons", "probe.svg")
        if os.path.exists(path):
            return QIcon(path)
        return QIcon()

    def _add_toolbar(self):
        tb = self.iface.addToolBar("NPN Explorer")
        tb.setObjectName("NpnExplorerToolbar")
        a = tb.addAction(self._icon(), "Explorador NPN")
        a.setCheckable(True)
        a.setChecked(True)
        a.setStatusTip("Panel y sonda: valor de columna bajo el cursor")
        a.toggled.connect(self._on_dock_toggled)
        return tb, a

    def _build_dock(self):
        self._dock = QDockWidget("Explorador NPN", self.iface.mainWindow())
        self._dock.setObjectName("NpnExplorerDock")
        w = QWidget()

        self._layer_combo = QgsMapLayerComboBox()
        self._layer_combo.setFilters(
            QgsMapLayerProxyModel.PointLayer
            | QgsMapLayerProxyModel.LineLayer
            | QgsMapLayerProxyModel.PolygonLayer
        )
        self._layer_combo.layerChanged.connect(self._on_layer_changed)

        self._field_combo = QgsFieldComboBox()
        self._field_combo.setLayer(self._layer_combo.currentLayer())
        self._field_combo.setAllowEmptyFieldName(False)
        self._field_combo.fieldChanged.connect(self._on_field_changed)

        self._value_field = _ValueLineEdit(self, w)
        self._value_field.setReadOnly(True)
        self._value_field.setPlaceholderText(
            "Activa la sonda; doble clic en el mapa o aquí para fijar el valor"
        )

        self._btn_probe = QPushButton("Sonda: activar")
        self._btn_probe.setCheckable(True)
        self._btn_probe.setChecked(False)
        self._btn_probe.toggled.connect(self._on_probe_toggled)

        form = QFormLayout()
        form.addRow("Capa vectorial:", self._layer_combo)
        form.addRow("Columna NPN:", self._field_combo)
        form.addRow("Valor NPN:", self._value_field)

        sep = QFrame()
        try:
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setFrameShadow(QFrame.Shadow.Sunken)
        except AttributeError:  # PyQt5
            sep.setFrameShape(QFrame.HLine)
            sep.setFrameShadow(QFrame.Sunken)

        lab_result = QLabel("Resultado del análisis")
        f = lab_result.font()
        f.setBold(True)
        lab_result.setFont(f)

        self._npn_error_label = QLabel()
        self._npn_error_label.setWordWrap(True)
        self._npn_error_label.setVisible(False)
        self._npn_value_labels = {}
        res_form = QFormLayout()
        try:
            res_form.setFieldGrowthPolicy(
                QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
            )
        except AttributeError:  # PyQt5
            try:
                res_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            except Exception:  # noqa: BLE001
                pass
        val_style_ok = "color: #1b5e20;"
        val_style_idle = "color: #757575;"
        for name in CAMPOS_NPN_ORDEN:
            vlab = QLabel("—")
            vlab.setWordWrap(True)
            vlab.setStyleSheet(val_style_idle)
            try:
                vlab.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                )
            except AttributeError:  # PyQt5
                vlab.setTextInteractionFlags(Qt.TextSelectableByMouse)
            res_form.addRow(f"{name}:", vlab)
            self._npn_value_labels[name] = vlab
        # guardar estilos para reutilizar en refresh
        self._npn_val_style_ok = val_style_ok
        self._npn_val_style_idle = val_style_idle

        result_panel = QWidget()
        result_panel.setLayout(res_form)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        try:
            scroll.setFrameShape(QFrame.Shape.NoFrame)
        except AttributeError:  # PyQt5
            scroll.setFrameShape(QFrame.NoFrame)
        try:
            scroll.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
        except AttributeError:
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(result_panel)
        scroll.setMaximumHeight(280)
        self._npn_result_scroll = scroll

        v = QVBoxLayout()
        v.addLayout(form)
        v.addWidget(sep)
        v.addWidget(lab_result)
        v.addWidget(self._npn_error_label)
        v.addWidget(scroll, 1)
        self._btn_copy = QPushButton()
        self._btn_copy.setObjectName("NpnCopyClipboardBtn")
        self._btn_copy.setIcon(_icon_copiar_portapapeles())
        self._btn_copy.setIconSize(QSize(20, 20))
        self._btn_copy.setFixedSize(32, 28)
        self._btn_copy.setToolTip("Copia el NPN y el desglose del análisis al portapapeles (texto plano).")
        self._btn_copy.setAccessibleName("Copiar al portapapeles")
        self._btn_copy.setStyleSheet("QPushButton#NpnCopyClipboardBtn { padding: 2px; }")
        self._btn_copy.clicked.connect(self._on_copy_npn_to_clipboard)
        v.addWidget(self._btn_copy, 0, Qt.AlignLeft)
        v.addWidget(self._btn_probe)
        w.setLayout(v)
        self._dock.setWidget(w)
        self._refresh_npn_analysis()

    def _on_copy_npn_to_clipboard(self):
        if self._unloaded:
            return
        lines = []
        raw = self._value_field.text() if self._value_field else ""
        lines.append("NPN (valor de capa)")
        lines.append(raw if raw.strip() else "(vacío o sin texto)")
        lines.append("")
        if self._npn_error_label is not None and self._npn_error_label.isVisible():
            err = (self._npn_error_label.text() or "").strip()
            if err:
                lines.append("Aviso / validación")
                lines.append(err)
                lines.append("")
        lines.append("Resultado del análisis")
        for name in CAMPOS_NPN_ORDEN:
            val = "—"
            if self._npn_value_labels and name in self._npn_value_labels:
                val = self._npn_value_labels[name].text()
            lines.append(f"  {name}: {val}")
        text = "\n".join(lines)
        QApplication.clipboard().setText(text)
        self.iface.messageBar().pushMessage(
            "NPN", "NPN y resultado del análisis copiados al portapapeles.",
            level=Qgis.Info,
            duration=2,
        )

    def _on_map_tool_set(self, new_tool, _old_tool=None):
        if self._unloaded or self._btn_probe is None or self._tool is None:
            return
        on = new_tool == self._tool
        self._btn_probe.blockSignals(True)
        self._btn_probe.setChecked(on)
        self._btn_probe.blockSignals(False)
        self._btn_probe.setText("Sonda: desactivar" if on else "Sonda: activar")

    def _on_dock_toggled(self, checked):
        if self._unloaded:
            return
        if self._dock is not None:
            self._dock.setVisible(checked)
        if not checked and self.iface.mapCanvas().mapTool() == self._tool:
            self.iface.mapCanvas().unsetMapTool(self._tool)

    def _on_probe_toggled(self, on):
        if self._unloaded:
            return
        if on:
            self._sync_tool_config()
            if self._layer_combo.currentLayer() is None:
                self.iface.messageBar().pushMessage(
                    "NPN", "Elige una capa vectorial.", level=1, duration=3
                )
                self._btn_probe.setChecked(False)
                return
            field = self._field_combo.currentField()
            if not field:
                self.iface.messageBar().pushMessage("NPN", "Elige una columna.", level=1, duration=3)
                self._btn_probe.setChecked(False)
                return
            self.iface.mapCanvas().setMapTool(self._tool)
            self._btn_probe.setText("Sonda: desactivar")
        else:
            self._clear_value_lock()
            if self.iface.mapCanvas().mapTool() == self._tool:
                self.iface.mapCanvas().unsetMapTool(self._tool)
            self._btn_probe.setText("Sonda: activar")

    def _on_layer_changed(self, _layer):
        if self._unloaded:
            return
        self._clear_value_lock()
        self._field_combo.setLayer(self._layer_combo.currentLayer())
        if self._btn_probe and self._btn_probe.isChecked():
            self._sync_tool_config()

    def _on_field_changed(self, _name):
        if self._unloaded or not self._btn_probe or not self._btn_probe.isChecked():
            return
        self._clear_value_lock()
        self._sync_tool_config()

    def _sync_tool_config(self):
        if self._unloaded or self._tool is None:
            return
        layer = self._layer_combo.currentLayer()
        name = self._field_combo.currentField()
        self._tool.set_target(
            layer, name, self._on_probe_value, self._on_map_double_click
        )

    def _on_map_double_click(self, _event):
        if self._unloaded or self._tool is None:
            return
        if self.iface.mapCanvas().mapTool() != self._tool:
            return
        self._toggle_value_lock()

    def _toggle_value_lock(self):
        if self._unloaded or self._value_field is None:
            return
        self._value_locked = not self._value_locked
        if self._value_locked:
            self._value_field.setStyleSheet("QLineEdit { background-color: #fff3cd; }")
            self._value_field.setToolTip(
                "Valor fijado. Doble clic otra vez (mapa o caja) para volver a actualizar con el cursor."
            )
        else:
            self._value_field.setStyleSheet("")
            self._value_field.setToolTip("")
        self._refresh_npn_analysis()

    def _clear_value_lock(self):
        if not self._value_locked:
            return
        self._value_locked = False
        if self._value_field is not None:
            self._value_field.setStyleSheet("")
            self._value_field.setToolTip("")

    def _npn_set_result_labels(self, idle=True):
        """Pone '—' en todos los desgloses. idle=True aplica estilo inactivo."""
        if not self._npn_value_labels:
            return
        for name in CAMPOS_NPN_ORDEN:
            self._npn_value_labels[name].setText("—")
            st = self._npn_val_style_idle if idle else self._npn_val_style_ok
            self._npn_value_labels[name].setStyleSheet(st)

    def _npn_reset_labels_idle(self):
        if not self._npn_value_labels:
            return
        self._npn_set_result_labels(idle=True)
        if self._npn_error_label is not None:
            self._npn_error_label.hide()
            self._npn_error_label.clear()

    def _refresh_npn_analysis(self):
        if self._unloaded or not self._npn_value_labels or self._value_field is None:
            return
        t = _normalize_value_text(self._value_field.text())
        if not t:
            self._npn_set_result_labels(idle=True)
            if self._npn_error_label is not None:
                self._npn_error_label.setText(MSG_NPN_VACIO_NULO)
                self._npn_error_label.setStyleSheet("color: #b71c1c;")
                self._npn_error_label.setVisible(True)
            return
        r = analizar_npn(t)
        if r.es_valido:
            if self._npn_error_label is not None:
                self._npn_error_label.hide()
                self._npn_error_label.clear()
            m = {k: v for k, v in r.filas}
            for name in CAMPOS_NPN_ORDEN:
                self._npn_value_labels[name].setText(
                    m.get(name, "—")
                )
                self._npn_value_labels[name].setStyleSheet(self._npn_val_style_ok)
        else:
            self._npn_reset_labels_idle()
            if r.error and self._npn_error_label is not None:
                self._npn_error_label.setText(r.error)
                self._npn_error_label.setStyleSheet("color: #b71c1c;")
                self._npn_error_label.setVisible(True)

    def _on_probe_value(self, value):
        if self._unloaded or self._value_field is None:
            return
        if self._value_locked:
            return
        is_empty = value is None
        if not is_empty and NULL is not None and value == NULL:
            is_empty = True
        if is_empty:
            self._value_field.clear()
        else:
            self._value_field.setText(str(value))
        self._refresh_npn_analysis()

    def unload(self):
        self._unloaded = True
        c = self.iface.mapCanvas()
        if self._map_tool_set_slot is not None:
            try:
                c.mapToolSet.disconnect(self._map_tool_set_slot)
            except Exception:  # noqa: BLE001 — Qt6 bindings (no siempre TypeError)
                pass
            self._map_tool_set_slot = None
        if c.mapTool() == self._tool:
            c.unsetMapTool(self._tool)
        self._tool = None

        if self._layer_combo is not None:
            self._layer_combo.blockSignals(True)
            try:
                self._layer_combo.layerChanged.disconnect(self._on_layer_changed)
            except Exception:  # noqa: BLE001
                pass
        if self._field_combo is not None:
            self._field_combo.blockSignals(True)
            try:
                self._field_combo.fieldChanged.disconnect(self._on_field_changed)
            except Exception:  # noqa: BLE001
                pass
        if self._btn_probe is not None:
            try:
                self._btn_probe.toggled.disconnect(self._on_probe_toggled)
            except Exception:  # noqa: BLE001
                pass
        if self._action is not None:
            try:
                self._action.toggled.disconnect(self._on_dock_toggled)
            except Exception:  # noqa: BLE001
                pass

        if self._toolbar is not None:
            if self._action is not None:
                self._toolbar.removeAction(self._action)
            tb = self._toolbar
            self._toolbar = None
            # Evitar setParent en barra añadida vía addToolBar; en su lugar QMainWindow o hide.
            mw = self.iface.mainWindow()
            if isinstance(mw, QMainWindow):
                try:
                    mw.removeToolBar(tb)
                except Exception:  # noqa: BLE001
                    pass
            tb.hide()
            tb.deleteLater()
        self._action = None

        if self._dock is not None:
            self.iface.removeDockWidget(self._dock)
            self._dock.deleteLater()
        self._dock = None
        self._layer_combo = None
        self._field_combo = None
        self._btn_probe = None
        self._btn_copy = None
        self._value_field = None
        self._npn_error_label = None
        self._npn_value_labels = None  # dict nombre_campo -> QLabel
        self._npn_result_scroll = None

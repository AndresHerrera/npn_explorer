# -*- coding: utf-8 -*-
"""Explorador NPN: lectura de atributo bajo el cursor."""


def classFactory(iface):
    from .npn_explorer import NpnExplorer
    return NpnExplorer(iface)

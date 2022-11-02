
import json
import sys

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

sys.path.insert(0, '/home/martin/qgis/git-master/build/output/python')

from qgis.core import *
from qgis.gui import *

"""
TODO:
- switch all / only active / only loaded / only loading queue / only active jobs
"""


filename = sys.argv[1] if len(sys.argv) > 1 else "/tmp/dump.json"

with open(filename) as f:
    data = json.load(f)

records = data["rec"]
t0 = QTime.fromString(data["timeStart"], "hh:mm:ss.zzz")


a = QgsApplication([], True)

QgsApplication.setPrefixPath('/home/martin/qgis/git-master/build/output', True)
QgsApplication.initQgis()


records_model = QStandardItemModel()
for rec in records:
    t1 = QTime.fromString(rec["timeStart"], "hh:mm:ss.zzz")
    t2 = QTime.fromString(rec["timeFinish"], "hh:mm:ss.zzz")
    t_start = t0.msecsTo(t1)/1000.
    duration = t1.msecsTo(t2)/1000.
    nodes_loading = rec["loading"]
    nodes_replacement = rec["replacement"]
    nodes_active = rec["active"]
    msg = "{:.3f} took {:.3f}s (loading {} | loaded {} | active {})".format(t_start, duration, len(nodes_loading), len(nodes_replacement), len(nodes_active))
    records_model.appendRow(QStandardItem(msg))



lyr = QgsVectorLayer("Polygon?field=node_id:string&field=state:integer&field=active:integer", "x", "memory")
lyr_camera = QgsVectorLayer("Point", "y", "memory")


def create_nodes_layer_renderer(load_queue, loading, loaded_active, loaded_inactive):
    s_green = QgsFillSymbol.createSimple({"color": "green"})
    s_green.setOpacity(0.3)
    s_yellow = QgsFillSymbol.createSimple({"color": "yellow"})
    s_yellow.setOpacity(0.3)
    s_red = QgsFillSymbol.createSimple({"color": "red"})
    s_red.setOpacity(0.3)
    s_blue = QgsFillSymbol.createSimple({"color": "blue"})
    s_blue.setOpacity(0.3)

    r_root = QgsRuleBasedRenderer.Rule(None)
    if load_queue:
        r_root.appendChild(QgsRuleBasedRenderer.Rule(s_red, 0, 0, "active=0 and state = -1"))
    if loading:
        r_root.appendChild(QgsRuleBasedRenderer.Rule(s_blue, 0, 0, "active=0 and state = -2"))
    if loaded_active:
        r_root.appendChild(QgsRuleBasedRenderer.Rule(s_green, 0, 0, "active=1"))
    if loaded_inactive:
        r_root.appendChild(QgsRuleBasedRenderer.Rule(s_yellow, 0, 0, "active=0 and state != -1 and state != -2"))
    rbr = QgsRuleBasedRenderer(r_root)
    lyr.setRenderer(rbr)

create_nodes_layer_renderer(True, True, True, True)

pal_settings = QgsPalLayerSettings()
pal_settings.fieldName = "node_id"
lyr.setLabeling(QgsVectorLayerSimpleLabeling(pal_settings))
lyr.setLabelsEnabled(True)


def populate_nodes_layer(record_index):

    record = records[record_index]
    loading = record["loading"]
    loaded = record["replacement"]
    jobs = record["jobs"]
    active = set(record["active"])
    camera_x, camera_y, camera_z = record["camera"]

    f_cam = QgsFeature()
    f_cam.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(camera_x,camera_z)))
    lyr_camera.dataProvider().truncate()
    lyr_camera.dataProvider().addFeatures([f_cam])

    features = []
    for n in loaded:
        f = QgsFeature(lyr.fields())
        x_min, y_min, z_min, x_max, y_max, z_max = n["bbox"]
        #print(bbox)
        f.setGeometry(QgsGeometry.fromRect(QgsRectangle(x_min,z_min,x_max,z_max)))
        f["node_id"] = n["id"]
        f["state"] = n["state"]
        f["active"] = n["id"] in active
        features.append(f)

    for n in loading:
        f = QgsFeature(lyr.fields())
        x_min, y_min, z_min, x_max, y_max, z_max = n["bbox"]
        f.setGeometry(QgsGeometry.fromRect(QgsRectangle(x_min,z_min,x_max,z_max)))
        f["node_id"] = n["id"]
        f["state"] = -1
        f["active"] = False
        features.append(f)

    for n in jobs:
        f = QgsFeature(lyr.fields())
        x_min, y_min, z_min, x_max, y_max, z_max = n["bbox"]
        f.setGeometry(QgsGeometry.fromRect(QgsRectangle(x_min,z_min,x_max,z_max)))
        f["node_id"] = n["id"]
        f["state"] = -2
        f["active"] = False
        features.append(f)

    lyr.dataProvider().truncate()
    lyr.dataProvider().addFeatures(features)


#populate_nodes_layer(-1)

class MainWnd(QWidget):

    def __init__(self):
        QWidget.__init__(self)
        self.v = QListView()
        self.v.setModel(records_model)

        self.mc = QgsMapCanvas()
        self.mc.setLayers([lyr_camera, lyr])
        self.mc.setExtent(QgsRectangle(-20000,-20000,20000,20000))

        self.v.selectionModel().currentChanged.connect(self.record_changed)

        self.tb = QToolBar("h")
        self.a_load_queue = QAction("waiting to load", self.tb)
        self.a_loading = QAction("loading", self.tb)
        self.a_loaded_active = QAction("loaded - active", self.tb)
        self.a_loaded_inactive = QAction("loaded - inactive", self.tb)
        for a in [self.a_load_queue,self.a_loading,self.a_loaded_active,self.a_loaded_inactive]:
            a.setCheckable(True)
            a.setChecked(True)
            a.triggered.connect(self.update_nodes_renderer)
            self.tb.addAction(a)

        lv = QVBoxLayout()
        lv.addWidget(self.tb)
        lv.addWidget(self.mc)

        l = QHBoxLayout()
        l.addWidget(self.v)
        l.addLayout(lv)
        self.setLayout(l)

    def record_changed(self, idx):
        row = idx.row()
        populate_nodes_layer(row)
        lyr.triggerRepaint()
        self.mc.refresh()

    def update_nodes_renderer(self):
        create_nodes_layer_renderer(self.a_load_queue.isChecked(), self.a_loading.isChecked(), self.a_loaded_active.isChecked(), self.a_loaded_inactive.isChecked())
        lyr.triggerRepaint()
        self.mc.refresh()



w = MainWnd()
w.show()

a.exec_()

# -*- coding: utf-8 -*-
"""
/***************************************************************************
 XYZMesh2CSVDialog
                                 A QGIS plugin
 XYZ形式CSV出力ダイアログ
                             -------------------
        copyright            : (C) 2023 by orbitalnet
 ***************************************************************************/

"""

import os
import math
import qgis.processing

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import QVariant
from PyQt5.QtWidgets import QFileDialog, QMessageBox

from qgis.core import *
from qgis.gui import *

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'xyzmesh2csv_dialog_base.ui'))


class XYZMesh2CSVDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, iface, parent=None):
        """Constructor."""
        super(XYZMesh2CSVDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.iface = iface

        # 対象レイヤをポリゴンに限定
        self.cmb_layer.setFilters( QgsMapLayerProxyModel.PolygonLayer  )
        self.cmb_layer2.setFilters( QgsMapLayerProxyModel.PolygonLayer  )

        # connect設定
        self.btn_run.clicked.connect(self.btn_run_clicked)
        self.btn_export.clicked.connect(self.btn_export_clicked)
        self.btn_select.clicked.connect(self.btn_select_clicked)
        self.btn_csv.clicked.connect(self.btn_csv_clicked)
        self.btn_select2.clicked.connect(self.btn_select2_clicked)
        self.btn_run2.clicked.connect(self.btn_run2_clicked)
        self.btn_close.clicked.connect(self.close)

    def closeEvent(self, event):
        """
        クローズ処理
        """
        self.deleteWorkLayer()
        event.accept()

    def btn_select_clicked(self):
        """
        選択ボタン処理

        選択ダイアログを表示する
        """
        if self.lbl_filepath.text() == "":
            # 実行ディレクトリ取得
            rootpath = os.path.abspath(os.path.dirname("__file__"))
        else:
            rootpath = self.lbl_filepath.text()

        # ディレクトリ選択ダイアログを表示
        path = QFileDialog.getExistingDirectory(None, "rootpath", rootpath)
        self.lbl_filepath.setText(path)


    def btn_run_clicked(self):
        """
        メッシュ作成実行ボタン処理
        
        XYZメッシュレイヤを作成する
        """
        # 対象地物を処理レイヤにコピー
        layer = self.cmb_layer.currentLayer()
        if layer == None:
            QMessageBox.information(self, 'Message', u"レイヤがありません。", QMessageBox.Ok)
            return        

        # すべて選択許可
        if self.chk_select_feature.isChecked() == True:
            layer.selectAll()

        slist = layer.getSelectedFeatures()
        # 選択地物がない場合
        if len(list(slist)) == 0:
            QMessageBox.information(self, 'Message', u"対象レイヤの地物を選択してください", QMessageBox.Ok)
            return        

        # 領域に対してXYZメッシュレイヤを作成
        tileset = TileSet(self.iface,layer,self.cmb_tilez.currentIndex()+1)
        tileset.count_tiles(tileset.get_first_tile())     

        slist = layer.getSelectedFeatures()
        geomlayer = QgsVectorLayer('Polygon?crs=epsg:4326', 'p2' , 'memory')
        geomlayerprov = geomlayer.dataProvider()
        for feature in slist :
            feat = QgsFeature()
            buffer = feature.geometry().buffer(0.0, 5)
            feat.setGeometry(buffer)
            geomlayerprov.addFeatures([feat])
        geomlayer.updateExtents()
        QgsProject.instance().addMapLayers([geomlayer])

        p1layer = QgsProject.instance().mapLayersByName('p1')[0]
        p2layer = QgsProject.instance().mapLayersByName('p2')[0]

        # 選択
        qgis.processing.run("native:selectbylocation", {'INPUT':p1layer,'PREDICATE':[0],'INTERSECT':p2layer,'METHOD':0})

        # 選択済み地物をCSV出力
        slist = p1layer.getSelectedFeatures()
        geomlayer = QgsVectorLayer('Polygon?crs=epsg:4326', 'メッシュレイヤー' , 'memory')
        geomlayerprov = geomlayer.dataProvider()
        geomlayerprov.addAttributes([QgsField("x", QVariant.Int),QgsField("y", QVariant.Int),QgsField("z", QVariant.Int)])
        geomlayer.updateFields() 

        for feature in slist :
            geomlayerprov.addFeatures([feature])

        geomlayer.updateExtents()
        QgsProject.instance().addMapLayers([geomlayer])           

        self.deleteWorkLayer_to12()


    def btn_export_clicked(self) :
        """
        CSVファイル作成実行ボタン処理
        
        CSVファイルを作成(出力)する
        """

        if self.lbl_filepath.text() == "":
            # パスが指定されていない場合
            QMessageBox.information(self, 'Message', u"出力フォルダを選択してください", QMessageBox.Ok)
            return

        if len(QgsProject.instance().mapLayersByName('メッシュレイヤー')) == 0 :
            # メッシュレイヤーが作成されていない場合
            QMessageBox.information(self, 'Message', u"メッシュレイヤーが存在しません", QMessageBox.Ok)
            return
        
        # XYZの数値を属性にする処理レイヤ作成
        geomlayer = QgsVectorLayer('Polygon?crs=epsg:4326', 'p3' , 'memory')
        geomlayerprov = geomlayer.dataProvider()
        geomlayerprov.addAttributes([QgsField("x", QVariant.Int),QgsField("y", QVariant.Int),QgsField("z", QVariant.Int)])
        geomlayer.updateFields() 

        layer = QgsProject.instance().mapLayersByName('メッシュレイヤー')[0]
        if self.chk_selectmesh.isChecked() :
            # [選択メッシュのみ]チェック時
            if len(list(layer.getSelectedFeatures())) == 0:
                # 選択地物がない場合
                QMessageBox.information(self, 'Message', u"メッシュレイヤーの地物を選択してください", QMessageBox.Ok)
                return   

            # 選択された地物を処理レイヤに追加
            selected_features = layer.getSelectedFeatures()
            geomlayerprov.addFeatures(selected_features)

        else :
            # 未チェック時
            selected_features = layer.getFeatures()
            geomlayerprov.addFeatures(selected_features)

        # 処理レイヤの領域更新とプロジェクトに追加
        geomlayer.updateExtents()
        QgsProject.instance().addMapLayers([geomlayer])           

        # 処理レイヤの情報をCSVに出力
        with open(self.lbl_filepath.text() + '/xyz.csv', mode='w') as f:
            for feature in geomlayer.getFeatures():
                f.write(str(feature['x']) + "," + str(feature['y']) + "," + str(feature['z']) + '\n' )

        # すべての処理レイヤを削除
        self.deleteWorkLayer()

        # 出力したCSVをレイヤとして追加
        self.loadLayer(self.lbl_filepath.text() + '/xyz.csv')

        # 処理終了
        QMessageBox.information(self, 'Message', u"出力しました", QMessageBox.Ok)


    def btn_csv_clicked(self):
        """
        CSVファイル読み込みの選択ボタン処理
        
        読み込むCSVファイルを選択する
        """
        spath,_ = QFileDialog.getOpenFileName(None, u'ファイル選択',None, "XYZメッシュファイル (*.csv)")
        if spath == "":
            return

        # CSVをレイヤとして追加
        self.loadLayer(spath)


    def loadLayer(self,spath) :
        """
        XYZメッシュファイルをベクターレイヤとして作成

        @param  spath:XYZメッシュファイルのパス
        """

        # ベクターレイヤ生成
        layername, ext = os.path.splitext(os.path.basename(spath))
        geomlayer = QgsVectorLayer('Polygon?crs=epsg:4326', layername, 'memory')
        geomlayerprov = geomlayer.dataProvider()
        geomlayerprov.addAttributes([QgsField("x", QVariant.Int),QgsField("y", QVariant.Int),QgsField("z", QVariant.Int)])
        geomlayer.updateFields() 

        # csvを読み込みレイヤに追加
        with open(spath, mode='r', encoding='utf-8-sig') as f:
            for s_line in f:
                attr = s_line.split(',')
                tile = Tile(int(attr[0]),int(attr[1]),int(attr[2]))
                feat = QgsFeature()
                feat.setGeometry(QgsGeometry.fromRect(tile.toRectangle()))
                feat.setAttributes([tile.x,tile.y,tile.z])
                geomlayerprov.addFeatures([feat])

        # 処理レイヤの領域更新とプロジェクトに追加
        geomlayer.updateExtents()
        QgsProject.instance().addMapLayers([geomlayer])


    def deleteWorkLayer(self):
        """
        すべての処理レイヤの削除
        """        
        p1layer = QgsProject.instance().mapLayersByName('p1')
        p2layer = QgsProject.instance().mapLayersByName('p2')
        p3layer = QgsProject.instance().mapLayersByName('p3')
        p4layer = QgsProject.instance().mapLayersByName('メッシュレイヤー')
        if len(p1layer) == 1:
            QgsProject.instance().removeMapLayer(p1layer[0])
        if len(p2layer) == 1:
            QgsProject.instance().removeMapLayer(p2layer[0])
        if len(p3layer) == 1:
            QgsProject.instance().removeMapLayer(p3layer[0])
        if len(p4layer) == 1:
            QgsProject.instance().removeMapLayer(p4layer[0])

    def deleteWorkLayer_to12(self):
        """
        p1,p2の処理レイヤの削除
        """
        p1layer = QgsProject.instance().mapLayersByName('p1')
        p2layer = QgsProject.instance().mapLayersByName('p2')
        if len(p1layer) == 1:
            QgsProject.instance().removeMapLayer(p1layer[0])
        if len(p2layer) == 1:
            QgsProject.instance().removeMapLayer(p2layer[0])


    def btn_select2_clicked(self):
        """
        選択メッシュ出力の出力フォルダの選択ボタン処理

        選択ダイアログを表示する
        """
        # 実行ディレクトリ取得
        rootpath = os.path.abspath(os.path.dirname("__file__"))
        # ディレクトリ選択ダイアログを表示
        path = QFileDialog.getExistingDirectory(None, "rootpath", rootpath)
        self.lbl_filepath2.setText(path)


    def btn_run2_clicked(self):
        """
        選択メッシュ出力の処理実行ボタン処理

        対象地物を処理レイヤにコピーする
        """

        layer = self.cmb_layer2.currentLayer()
        # 選択地物がない場合
        if len(list(layer.getSelectedFeatures())) == 0:
            QMessageBox.information(self, 'Message', u"対象レイヤの地物を選択してください", QMessageBox.Ok)
            return        
        
        # パスが指定されていない場合
        if self.lbl_filepath2.text() == "":
            QMessageBox.information(self, 'Message', u"出力フォルダを選択してください", QMessageBox.Ok)
            return

        fields = layer.fields()
        if fields.indexOf('x') == -1:
            QMessageBox.information(self, 'Message', u"フィールド名が不正です", QMessageBox.Ok)
            return

        if fields.indexOf('y') == -1:
            QMessageBox.information(self, 'Message', u"フィールド名が不正です", QMessageBox.Ok)
            return

        if fields.indexOf('z') == -1:
            QMessageBox.information(self, 'Message', u"フィールド名が不正です", QMessageBox.Ok)
            return

        # 選択地物を１つづつ出力する
        with open(self.lbl_filepath2.text() + '/' + layer.name() + '.csv', mode='w') as f:
            for feature in layer.getSelectedFeatures():
                f.write(str(feature['x']) + "," + str(feature['y']) + "," + str(feature['z']) + '\n' )

        # 出力したCSVをレイヤとして追加
        self.loadLayer(self.lbl_filepath2.text() + '/' + layer.name() + '.csv')

        # 処理終了
        QMessageBox.information(self, 'Message', u"出力しました", QMessageBox.Ok)


class Tile:
    """
    タイルオブジェクトクラス
    """    
    def __init__(self, x=0, y=0, z=0):
        self.x = x
        self.y = y
        self.z = z
        self.y_tms = int(2.0**z - y - 1)

    def toPoint(self):
        """
        タイルのxyzから点オブジェクトを生成
        """    
        n = math.pow(2, self.z)
        longitude = float(self.x) / n * 360.0 - 180.0
        latitude = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * float(self.y) / n))))
        return QgsPointXY(longitude, latitude)

    def toRectangle(self):
        """
        矩形オブジェクトを生成
        """    
        return QgsRectangle(self.toPoint(), Tile(self.x + 1, self.y + 1, self.z).toPoint())

class TileSet:
    """
    タイル処理クラス
    """    
    def __init__(self, iface, layer, z):
        self.extents = layer.boundingBoxOfSelected()

        self.minZoom = z
        self.maxZoom = z
        self.zoom_ranges = range(self.minZoom, self.maxZoom + 1)
        self.tile_width = 256
        self.tile_height = 256
        self.tiles = []
        self.meshlayer = QgsVectorLayer('Polygon?crs=epsg:4326', 'p1' , 'memory')
        self.meshlayerprov = self.meshlayer.dataProvider()   
        self.meshlayerprov.addAttributes([QgsField("x", QVariant.Int),QgsField("y", QVariant.Int),QgsField("z", QVariant.Int)])
        self.meshlayer.updateFields() 
 

    def get_first_tile(self):
        """
        初期状態のタイル生成
        """
        return Tile(0, 0, 0)


    def count_tiles(self, tile):
        """
        領域内の指定ズーム内のタイルに対し、xyzを数値にした属性の地物を追加する

        @param tile:タイルオブジェクト
        """        
        if not self.extents.intersects(tile.toRectangle()):
            # 交差なし
            return
        if self.minZoom <= tile.z and tile.z <= self.maxZoom:
            # 指定ズーム内の領域
            self.tiles.append(tile)

            # 地物生成して追加
            feat = QgsFeature()
            feat.setGeometry(QgsGeometry.fromRect(tile.toRectangle()))
            feat.setAttributes([tile.x,tile.y,tile.z])
            self.meshlayerprov.addFeatures([feat])

            self.meshlayer.updateExtents()

        # 再帰的に処理
        if tile.z < self.maxZoom:
            for x in range(2 * tile.x, 2 * tile.x + 2, 1):
                for y in range(2 * tile.y, 2 * tile.y + 2, 1):
                    sub_tile = Tile(x, y, tile.z + 1)
                    self.count_tiles(sub_tile)
        QgsProject.instance().addMapLayers([self.meshlayer])

        return self.tiles

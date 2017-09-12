# -*- coding: utf-8 -*-
"""
/***************************************************************************
 AlBADockWidget
                                 A QGIS plugin
 Bestandsdatenauskunft zu ALKIS Flurstücken
                             -------------------
        begin                : 2016-02-08
        git sha              : $Format:%H$
        copyright            : (C) 2016 by Jochen Schwarze / GIS_WG
        email                : info@giswg.de
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os, sys, datetime
import traceback
import xlwt, csv, codecs
import psycopg2
#import dbConnection

from PyQt4 import QtGui, uic
from PyQt4 import QtCore
from PyQt4.QtCore import *
from PyQt4.QtGui import *

from qgis.utils import *
from qgis.core import *
from qgis.gui import *

from albeda_alkis_ct import kt_blattart, buch_art, rechtsgemeinschaft_art, kt_anrede, eigentuemer_art, bundeslaender

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'al_ba_dockwidget_base.ui'))

class AlBADockWidget(QtGui.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(AlBADockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect

	self.setupUi(self)

        self.settings = QSettings()

        #ProgressBar
        self.progressBar.setRange(0, 100)

        #Alle Tab Widgets
        self.tw_suche_auswahl.currentChanged.connect(self.keepCurrentTab)
        self.tw_result_setup.currentChanged.connect(self.keepCurrentTab)
        self.tw_setup.currentChanged.connect(self.keepCurrentTab)

        #Tab: Karte
        self.pb_bestand_sel.clicked.connect(self.getFlurstueckeFromMapSelection)
        self.pb_anlieger.clicked.connect(self.getAnliegerFromSelection)
        self.pb_add_komm_flst.clicked.connect(self.addKommFlst)

        #Tab: Koordinaten
        self.cb_crd_fmt.activated.connect(self.setCrdFmt)
        self.cb_epsg.activated.connect(self.setCrdEPSG)
        self.pb_sel_flst_coords.clicked.connect(self.selFlstAtCoords)
        self.pb_query_flst_coords.clicked.connect(self.qryFlstAtCoords)
        self.pb_goto_coord.clicked.connect(self.gotoFlstAtCoords)
        self.tb_switch_coord.clicked.connect(self.switchCoordinates)
        self.tb_blink_coord.clicked.connect(self.blinkCoord)

        #Tab: Flurst.
        self.pb_flst_auswahl.clicked.connect(self.selFlst)
        self.pb_flst_goto.clicked.connect(self.gotoFlst)
        self.pb_flst_abfrage.clicked.connect(self.findFlurstuecke)
        self.cb_gemarkung.activated.connect(self.findFlurstueckeLive)
        self.le_nenner.textChanged.connect(self.findFlurstueckeLive)
        self.le_zaehler.textChanged.connect(self.findFlurstueckeLive)
        self.tw_flst_livesearch.horizontalHeader().setResizeMode(QtGui.QHeaderView.ResizeToContents)

        #Tab: Adresse
        self.cb_str.activated.connect(self.setStr)
        self.le_str.textChanged.connect(self.strasseSelect)
        self.tb_goto_str.clicked.connect(self.geheZuStrasse)
        self.tb_blink_str.clicked.connect(self.strHervorheben)
        self.pb_get_flst_from_hnr.clicked.connect(self.getFlstFromAdr)
        self.pb_show_hnr.clicked.connect(self.showHnr)
        self.radioButton_XOR.setEnabled(False)

        #Tab: Eigentümer
        self.pb_find_person.clicked.connect(self.findeFlstZuEigentuemer)
        self.cb_3rd_beg_recht.clicked.connect(self.activate3rdRecht)

        #Tab: Tree
        self.pushButton_gotoTree.clicked.connect(self.gotoGeometry)
        self.pushButton_zoomTree.clicked.connect(self.zoomGeometry)
        self.pushButton_cleanTree.clicked.connect(self.cleanTree)
        self.treeWidget.itemSelectionChanged.connect(self.treeItemGeKlicked)
        self.treeWidget.setHeaderHidden(True)

        #Tab: Table
        self.pushButton_gotoTable.clicked.connect(self.gotoGeometry)
        self.pushButton_zoomTable.clicked.connect(self.zoomGeometry)
        self.pushButton_cleanTable.clicked.connect(self.cleanTabelle)
        self.pushButton_exportTable.clicked.connect(self.exportTable)
        self.tableWidget.itemSelectionChanged.connect(self.tableItemGeKlicked)
        self.tableWidget.verticalHeader().sectionClicked.connect(self.tableHeaderGeKlicked)
        self.tableWidget.horizontalHeader().setResizeMode(QtGui.QHeaderView.ResizeToContents)

        #Tab: Einstellungen-Database
        self.comboBox_dbConnections.activated.connect(self.getDbConnectionFromNameCombo)
        self.pushButton_dbUpdate.clicked.connect(self.updateDBConnections)
        self.pushButton_axflst_det.clicked.connect(self.findAxFlurstueckLayer)

        #Tab: Einstellungen-Tabelle
        self.cb_query_headline.stateChanged.connect(self.displayTableHeaderChange)

        #Tab: Einstellungen-Farben
        self.pb_col_komm_flst.clicked.connect(self.defineKommFlstColor)
        self.pb_col_headers.clicked.connect(self.defineTableHeaderColor)
        self.pb_col_alt_flst.clicked.connect(self.defineTableAlteringRowColor)
        self.pb_col_tab_bg.clicked.connect(self.defineTableBackgroudColor)
        self.pb_col_highlight_flst.clicked.connect(self.defineFlstHighlightColor)
        self.pb_col_highlight_hnr.clicked.connect(self.defineHnrHighlightColor)
        self.hs_col_opac_highlight_flst.valueChanged.connect(self.defineFlstHighlightOpacity)
        self.hs_col_opac_highlight_hnr.valueChanged.connect(self.defineHnrHighlightOpacity)
        self.hs_col_opac_kommflst.valueChanged.connect(self.defineKommFlstOpacity)



        self.toggleBedienelemente(False)

        QgsMapLayerRegistry.instance().layersRemoved.connect(self.getDbConnectionFromNameCombo)
        QgsMapLayerRegistry.instance().layersAdded.connect(self.getDbConnectionFromNameCombo)

        #Eingabewidgets für Koordindatensuche
        self.x_metr = QLineEdit()
        self.x_deg = QLineEdit()
        self.x_min = QLineEdit()
        self.x_sec = QLineEdit()
        self.y_metr = QLineEdit()
        self.y_deg = QLineEdit()
        self.y_min = QLineEdit()
        self.y_sec = QLineEdit()
        self.lx_metr = QLabel()
        self.lx_metr.setText(u'm')
        self.lx_deg = QLabel()
        self.lx_deg.setText(u'°')
        self.lx_min = QLabel()
        self.lx_min.setText(u"'")
        self.lx_sec = QLabel()
        self.lx_sec.setText(u"''")
        self.ly_metr = QLabel()
        self.ly_metr.setText(u'm')
        self.ly_deg = QLabel()
        self.ly_deg.setText(u'°')
        self.ly_min = QLabel()
        self.ly_min.setText(u"'")
        self.ly_sec = QLabel()
        self.ly_sec.setText(u"''")

        #Klassenvariablen
        self.rubberBand = []
        self.rubberHnr = []
        self.rubberCoordTemp = []
        self.tableHeaders = []
        self.highlightedBereich = None
        self.rubberBandColorStyle = None
        self.kommFlstLayer = None
        self.canvas = iface.mapCanvas()
        self.curCrs = self.canvas.mapRenderer().destinationCrs().authid().split(':')[1]
        self.canvas.mapRenderer().setProjectionsEnabled(True)

        self.buch_art = buch_art
        k_buch_art = self.buch_art.keys()
        k_buch_art.sort()
        for k in k_buch_art:
            eintrag = u'%s:%s' % (k,self.buch_art[k])
            self.listWidget_eigentum_alle.addItem(eintrag)
            self.listWidget_eigentum_3rd_recht.addItem(eintrag)

        self.kt_blattart = kt_blattart
        self.rechtsgemeinschaft_art = rechtsgemeinschaft_art
        self.kt_anrede = kt_anrede
        self.eigentuemer_art = eigentuemer_art
        self.bundeslaender = bundeslaender

        self.cleanTabelle()

        self.updateDBConnections()

        self.restoreColorSettings()

        #setup combo boxen koordinatenformat und epsg codes
        epsglist = [u'31468 (DEGK4)',u'4326 (WGS84LL)',u'25832 (ETRS89/32N)']
        self.fmtlist = {u'metrisch':['metr'],
                   u"D.DDD°":['deg'],
                   u"D°M.MMM'":['deg', 'min'],
                   u"D°M'S.SSS''":['deg', 'min', 'sec']}

        for e in epsglist:
            self.cb_epsg.addItem(e)
        for f in self.fmtlist.keys():
            self.cb_crd_fmt.addItem(f)

        crd_fmt = self.settings.value('albeda/crd_fmt')
        if not crd_fmt:
            self.settings.setValue('albeda/crd_fmt', u'metrisch')
        else:
            self.cb_crd_fmt.setCurrentIndex(self.cb_crd_fmt.findText(crd_fmt))

        epsg = self.settings.value('albeda/crd_epsg')
        if not crd_fmt:
            self.settings.setValue('albeda/crd_epsg', u'31468 (DEGK4)')
        else:
            self.cb_epsg.setCurrentIndex(self.cb_epsg.findText(epsg))
        self.setCrdFmt()

        #restore current tabs
        for t in ['tw_suche_auswahl', 'tw_setup', 'tw_result_setup']:
            n = self.settings.value('albeda/tabs/%s' % t)
            if n:
                exec('self.%s.setCurrentIndex(n)' % t)

    def toggleBedienelemente(self, db_selected):
        self.pb_bestand_sel.setEnabled(db_selected)
        self.pb_anlieger.setEnabled(db_selected)

        self.pb_sel_flst_coords.setEnabled(db_selected)
        self.pb_query_flst_coords.setEnabled(db_selected)

        self.pb_flst_abfrage.setEnabled(db_selected)
        self.pb_flst_auswahl.setEnabled(db_selected)
        self.pb_flst_goto.setEnabled(db_selected)

        self.cb_str.setEnabled(db_selected)
        self.le_str.setEnabled(db_selected)
        self.tb_goto_str.setEnabled(db_selected)
        self.tb_blink_str.setEnabled(db_selected)
        self.pb_get_flst_from_hnr.setEnabled(db_selected)
        self.pb_show_hnr.setEnabled(db_selected)

        self.pb_find_person.setEnabled(db_selected)
        self.cb_3rd_beg_recht.setEnabled(db_selected)

    def setCrdFmt(self):
        crd_key = self.cb_crd_fmt.currentText()
        self.settings.setValue('albeda/crd_fmt', crd_key)
        #Clear layout
        col = range(self.gl_coords.columnCount())
        for c in col[1:-1]:
            for r in [0, 1]:
                i = self.gl_coords.itemAtPosition(r, c)
                if i:
                    widgetToRemove = i.widget()
                    self.gl_coords.removeWidget(widgetToRemove)
                    widgetToRemove.setParent(None)
        #clear widgets
        for c in ['metr','deg','min','sec']:
            for r in ['x', 'y']:
                exec ("""self.%s_%s.clear()""" % (r, c))
        #re-add widgets
        c = 1
        for le in self.fmtlist[crd_key]:
            exec("""self.gl_coords.addWidget(self.x_%s, 0, c)""" % le)
            exec("""self.gl_coords.addWidget(self.lx_%s, 0, c + 1)""" % le)
            exec("""self.gl_coords.addWidget(self.y_%s, 1, c)""" % le)
            exec("""self.gl_coords.addWidget(self.ly_%s, 1, c + 1)""" % le)
            c += 2

    def setCrdEPSG(self):
        s = self.sender()
        self.settings.setValue('albeda/crd_epsg', s.currentText())

    def updateDBConnections(self):
        # populate the combo with connections
        # 2do abfangen, dass auf pg_admin ebene eine datenbank umbenannt wurde
        # connection ist dann ungültig
        self.comboBox_dbConnections.clear()
        s = QSettings()
        s.beginGroup("PostgreSQL/connections")
        dbnames = s.childGroups()
        s.endGroup()
        #Für alle verfügbaren DBs prüfen ob ALKIS DB, und ALKIS DBs zählen
        alkis_db_ct = 0
        err_db = []
        for d in dbnames:
            #print d
            p = self.getDBParametersFromName(d)
            try:
                if self.isALKIS(p):
                    self.comboBox_dbConnections.addItem(d)
                    alkis_db_ct += 1
            except:
                err_db.append((d, p))

        #Fehlermeldung, wenn fehlerhafte datenbankverbindungen existieren
        if len(err_db) > 0:
            mb = QMessageBox()
            mb.setWindowTitle('Hinweis')
            mb.setIcon(QMessageBox.Information)
            mb.setText(u'Fehlerhafte oder ungültige DB Verbindungen!')
            mb.setInformativeText(str(err_db))
            mb.setStandardButtons(QMessageBox.Ok)
            ret = mb.exec_()

        #Fallunterscheidung für 0, 1 oder n ALKIS DBs
        if alkis_db_ct == 1:
            #genau eine ALKIS-DB
            #dann wird diese automatisch gewählt und albeda/dbconname entsprechend gesetzt
            self.pgConName = self.comboBox_dbConnections.currentText()
            self.pgConParam = self.getDbConnectionFromNameCombo()
        elif alkis_db_ct > 1:
            self.comboBox_dbConnections.insertItem(0, u'Datenbankverbindung wählen...')
        elif alkis_db_ct == 0:
            mb = QMessageBox()
            mb.setWindowTitle('Hinweis')
            mb.setIcon(QMessageBox.Information)
            mb.setText(u'Keine ALKIS-Datenbanken gefunden' % dbCon)
            mb.setInformativeText("""Es wurden keine Verbindungen zu Datenbanken gefunden, die eine ax_flurstueck Tabelle enthalten.
            Fragen Sie ggf. Ihren GIS Fachadministrator, wie man eine solche Verbindung herstellt.""")
            mb.setStandardButtons(QMessageBox.Ok)
            ret = mb.exec_()
        
        lastdbname = self.settings.value(u'albeda/dbconname')
        #Problem, wenn es >1 ALKIS DB gibt, aber noch kein albeda/dbconname
        i = self.comboBox_dbConnections.findText(lastdbname)
        if i > -1:
            self.comboBox_dbConnections.setCurrentIndex(i)
            self.pgConName = lastdbname
            self.getDbConnectionFromNameCombo()
        else:
            self.comboBox_dbConnections.setCurrentIndex(self.comboBox_dbConnections.findText(u'Datenbankverbindung wählen...'))
            self.pgConName = None
            self.pgConParam = ('','','','','')

        #fehler: letzte db verbindung exitiert nicht mehr
        #print self.pgConParam

    def isALKIS(self, param):
        # Funktion stellt Verbindung zur db jeweils selbst her, weil die Verbindungsdaten
        # auf Klasenebene noch nicht zur Verfügung stehen.
        # (ZUERST wird die db geprüft und DANN der Liste hinzugefügt)
        # daher geht execSQL hier auch noch nicht
        res = self.execSQLWithParam("""SELECT * FROM pg_class
                        WHERE relname IN ('ax_flurstueck', 'ax_buchungsstelle', 'ax_buchungsblatt', 'ax_namensnummer', 'ax_person') AND reltuples > 0""", param)
        #print len(res)
        return len(res) == 5 #impliziert dass alle fünf relationen vorhanden sind und daten enthalten

    def kommunaleFlstViewExists(self):
        exists = False
        try:
            res = self.execSQL("""SELECT * FROM pg_class WHERE relname = 'ax_flst_er' AND reltuples > 0""")
            # print len(res)
            exists = len(res) > 0  # impliziert dass alle fünf relationen vorhanden sind und daten enthalten
        except:
            pass
        return exists

    def findKommFlstLayer(self):
        dbName = self.pgConParam[0]
        lKeys = QgsMapLayerRegistry.instance().mapLayers().keys()
        res = False
        for k in lKeys:
            l = QgsMapLayerRegistry.instance().mapLayers()[k]
            try: #abfangen, wenn dataProvider vom Typ QgsRasterDataProvider ist
                uri = l.dataProvider().dataSourceUri()
                if 'dbname=\'%s\'' % dbName in uri and 'table="public"."ax_flst_er"' in uri:
                    self.kommFlstLayer = l
                    res = True
                    break
            except:
                pass
        #print res
        self.pb_add_komm_flst.setEnabled(not res)
        self.hs_col_opac_kommflst.setEnabled(res)
        self.pb_col_komm_flst.setEnabled(res)

    def findAxFlurstueckLayer(self):
        dbName = self.pgConParam[0]
        lKeys = QgsMapLayerRegistry.instance().mapLayers().keys()
        allKeys = len(lKeys)
        count = 0.0
        self.progressBar.setValue(count)
        res = False
        for k in lKeys:
            l = QgsMapLayerRegistry.instance().mapLayers()[k]
            try: #abfangen, wenn dataProvider vom Typ QgsRasterDataProvider ist
                f = l.dataProvider().fieldNameMap().keys()
                if 'dbname=\'%s\'' % dbName in l.dataProvider().dataSourceUri() and ('nenner' in f) and ('zaehler' in f) and ('gemarkungsnummer' in f) and ('amtlicheflaeche' in f) and ('istgebucht') in f:
                    self.lineEdit_ax_flst_layer.setText(l.name())
                    self.progressBar.setValue(100)
                    res = True
                    break
                count += 1
            except:
                pass
            self.progressBar.setValue((count/allKeys)*100)
        if not res:
            self.lineEdit_ax_flst_layer.setText('')
            mb = QMessageBox()
            mb.setWindowTitle('Hinweis')
            mb.setIcon(QMessageBox.Information)
            mb.setText(u'ax_flurstueck Layer fehlt für Datenbankverbindung "%s".' % dbName)
            mb.setInformativeText(u"""Der Layer wird benötigt, um hiervon Flurstückauswahlen treffen zu können.\nMöchten Sie den Layer ax_Flurstueck nun hinzuzufügen?""")
            mb.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            ret = mb.exec_()
            if ret == 1024:
                #print('Ok')
                uri = QgsDataSourceURI()
                database, host, port, username, password = self.pgConParam
                uri.setConnection("%s" % host, "%s" % port, "%s" % database, "%s" % username, "%s" % password)
                uri.setDataSource("public", "ax_flurstueck", "wkb_geometry")
                vlayername = u"Flurstück Auskunft (%s)" % dbName
                self.lineEdit_ax_flst_layer.setText(vlayername)
                layer = QgsVectorLayer(uri.uri(False), vlayername, "postgres")
                #set style
                r = layer.rendererV2()
                s = QgsFillSymbolV2.createSimple({'style':'no', 'outline_style':'no'})
                r.setSymbol(s)
                root = QgsProject.instance().layerTreeRoot()
                QgsMapLayerRegistry.instance().addMapLayer(layer, False) #zur Registry hinzufügen, aber nicht zum Layer Tree
                l = root.insertLayer(0, layer) #layer an position 0 einsortieren
                iface.setActiveLayer(layer)
                res = True
        if res:
            self.toggleBedienelemente(True)
            if not self.kommunaleFlstViewExists():
                self.pb_add_komm_flst.setEnabled(False)
                self.hs_col_opac_kommflst.setEnabled(False)
                self.pb_col_komm_flst.setEnabled(False)

    def getDbConnectionFromNameCombo(self):
        #definiert auf Klassenebene
        #   PostGIS Verbindungsname
        #   PostGIS Verbindungsparameter
        #   PostGIS Verbindung
        #   db connections must have username and pwd saved!
        self.pgConName = self.comboBox_dbConnections.currentText()
        self.settings.setValue("albeda/dbconname", self.pgConName)
        self.lineEdit_ax_flst_layer.clear()
        if not self.pgConName == u'Datenbankverbindung wählen...':
            #print self.pgConName
            self.pgConParam = self.getDBParametersFromName(self.pgConName)

            self.pgConn = psycopg2.connect("dbname='%s' host='%s' port='%s' user='%s' password='%s'" % self.pgConParam)

            #Bundesland ermitteln
            self.landkey = self.execSQL("""SELECT land FROM ax_flurstueck LIMIT 1""")[0][0]
            self.setWindowTitle('ALBeDA v%s - ALKIS Bestandsdatenauskunft (%s)' % (self.getPluginVersion(), self.bundeslaender[self.landkey]))
            self.populateGmkCombo()
            self.populateStrCombo()

            #ax_flurstueck layer und kommunales Grundeigentum finden
            self.findAxFlurstueckLayer()
            if not self.kommunaleFlstViewExists():
                self.pb_add_komm_flst.setEnabled(False)
                self.hs_col_opac_kommflst.setEnabled(False)
                self.pb_col_komm_flst.setEnabled(False)
            else:
                self.findKommFlstLayer()

            #norGIS ALKIS Plugin konfigurieren
            db, host, port, user, pwd = self.pgConParam
            try:
                s = QSettings('norBIT', 'norGIS-ALKIS-Erweiterung')
                s.setValue('host', host)
                s.setValue('port', port)
                s.setValue('dbname', db)
                s.setValue('uid', user)
                s.setValue('pwd', pwd)
            except:
                mb = QMessageBox()
                mb.setWindowTitle('Hinweis')
                mb.setIcon(QMessageBox.Information)
                mb.setText(u'norGIS ALKIS Plugin nicht installiert?')
                mb.setStandardButtons(QMessageBox.Ok)
                ret = mb.exec_()
        else:
            self.toggleBedienelemente(False)

    def getDBParametersFromName(self, conname):
        database = self.settings.value('PostgreSQL//connections//%s//database' % conname)
        username = self.settings.value('PostgreSQL//connections//%s//username' % conname)
        password = self.settings.value('PostgreSQL//connections//%s//password' % conname)
        host = self.settings.value('PostgreSQL//connections//%s//host' % conname)
        port = self.settings.value('PostgreSQL//connections//%s//port' % conname)
        return (database, host, port, username, password)

    def execSQL(self, sql):
        cur = self.pgConn.cursor()
        cur.execute(sql)
        return cur.fetchall()

    def execSQLWithParam(self, sql, param):
        con = psycopg2.connect("dbname='%s' host='%s' port='%s' user='%s' password='%s'" % param)
        cur = con.cursor()
        cur.execute(sql)
        return cur.fetchall()

    def populateStrCombo(self):
        self.cb_str.clear()
        self.strassenList = []

        # Freistaat Bayern
        if self.landkey == u'09':
            strassenListSQL = self.execSQL("""SELECT DISTINCT unverschluesselt
                                              FROM ax_lagebezeichnungmithausnummer ORDER BY unverschluesselt;""")
        #Baden Württemberg
        elif self.landkey == u'08':
            #strassennamen
            strassenListSQL = self.execSQL("""SELECT bezeichnung
                                              FROM ax_lagebezeichnungkatalogeintrag
                                              WHERE lage IN
                                                  (SELECT DISTINCT lage FROM ax_lagebezeichnungmithausnummer) ORDER BY bezeichnung;""")
        else:
            strassenListSQL = [] #2do alle anderen Bundesländer

        for s in strassenListSQL:
            self.cb_str.addItem(s[0])
            self.strassenList.append(s[0])

    def populateGmkCombo(self):
        self.gemarkung_ct = {}
        self.cb_gemarkung.clear()
        gemList = self.execSQL("""SELECT DISTINCT f.gemarkungsnummer, g.bezeichnung
                                  FROM ax_flurstueck AS f LEFT OUTER JOIN ax_gemarkung AS g ON f.gemarkungsnummer = g.gemarkungsnummer ORDER BY gemarkungsnummer""")
        self.cb_gemarkung.addItem('alle Gemarkungen')
        for key, bez in gemList:
            self.gemarkung_ct[key] = bez
            self.cb_gemarkung.addItem('%s %s' % (key, bez))

    def displayTableHeaderChange(self, state):
        self.cb_highlight_headline.setEnabled(self.cb_query_headline.isChecked())

    def tableItemGeKlicked(self):
        items = self.tableWidget.selectedItems()
        if len(items) > 0:
            row = items[0].row() #print "table item geklicked"
            testTableRow = row
            i = self.tableWidget.item(row, 0).text() #y,x???
            while i == u'':
                row -= 1
                i = self.tableWidget.item(row, 0).text()
            flstnr = self.tableWidget.item(row, 0).text()
            self.highlightFlst([flstnr])
            self.highlightTableRange(testTableRow)
        
    def tableHeaderGeKlicked(self, row):
        #print "table header geklicked"
        testTableRow = row
        i = self.tableWidget.item(row, 0).text() #y,x???.
        while i == u'':
            row -= 1
            i = self.tableWidget.item(row, 0).text()
        flstnr = self.tableWidget.item(row, 0).text()
        self.highlightFlst([flstnr])
        self.highlightTableRange(testTableRow)

    def treeItemGeKlicked(self):
        items = self.treeWidget.selectedItems()
        if len(items) > 0:
            item = items[0]
            if item.parent() == None:
                flist = []
                if self.cb_highlight_all.isChecked():
                    for n in range(item.childCount()):
                        flist.append(item.child(n).text(0))
            else:
                text = item.text(0)
                while len(text) > 20:
                    item = item.parent()
                    text = item.text(0)
                flist = [text]
            self.highlightFlst(flist)

    def highlightTableRange(self, testRow):
        # neuen Bereich suchen
        #print testRow

        startRow = testRow
        testtxt = self.tableWidget.item(testRow, 0).text()
        i = testtxt
        if testRow == 0:
            startRow = 0
        elif testtxt != u'' and self.tableWidget.item(testRow - 1, 0).text() != testtxt:
            startRow = testRow
        elif testtxt == u'' and self.tableWidget.item(testRow - 1, 0).text() != testtxt:
            startRow = testRow-1
        else:
            while i == testtxt and startRow > 0:
                startRow -= 1
                i = self.tableWidget.item(startRow, 0).text()

        if testRow == self.tableWidget.rowCount() - 1:
            endRow = testRow
        else:
            endRow = testRow + 1 #eine Zeile unter der gewählten anfangen, das Ende zu suchen
            i = self.tableWidget.item(endRow, 0).text()
            if self.tableWidget.item(endRow, 0).text() != testtxt:
                endRow = testRow
            else:
                while (i == u'' or i == testtxt) and endRow < self.tableWidget.rowCount() - 1:
                    endRow += 1
                    i = self.tableWidget.item(endRow, 0).text()

    def addKommFlst(self):
        #print 'add flst', self.pgConParam
        uri = QgsDataSourceURI()
        database, host, port, username, password = self.pgConParam
        uri.setConnection("%s" % host, "%s" % port, "%s" % database, "%s" % username, "%s" % password)
        uri.setDataSource("public", "ax_flst_er", "wkb_geometry")
        vlayername = u"Städtische Flurstücke"
        layer = QgsVectorLayer(uri.uri(False), vlayername, "postgres")
        # set style
        r = layer.rendererV2()
        c = self.kommFlstColor
        s = QgsFillSymbolV2.createSimple({'style': 'solid', 'outline_style': 'no',
                                          'color': '%s,%s,%s,%s' % (c.red(), c.green(), c.blue(), c.alpha())})
        #print '%s,%s,%s,%s' % (c.red(), c.green(), c.blue(), c.alpha())
        s.setColor(c)
        r.setSymbol(s)
        #r.symbol().symbolLayers()[0].setColor(self.kommFlstColor)
        root = QgsProject.instance().layerTreeRoot()
        QgsMapLayerRegistry.instance().addMapLayer(layer, False)  # zur Registry hinzufügen, aber nicht zum Layer Tree
        l = root.insertLayer(1, layer)  # layer an position 0 einsortieren
        self.hs_col_opac_kommflst.setEnabled(True)
        self.pb_col_komm_flst.setEnabled(True)
        self.kommFlstLayer = layer

    def highlightFlst(self, flist):
        canvas = iface.mapCanvas()

        #Gummibandliste löschen

        self.deleteRubber(self.rubberBand)
        self.rubberBand = []

        cur = self.pgConn.cursor()

        alle = float(len(flist))
        count = 0.0
        self.progressBar.setValue(0)

        minx = None
        miny = None
        maxx = None
        maxy = None

        for f in flist:
            gem, zn = f.split('-')
            z, n = zn.split('/')

            sql_stmnt = """
                SELECT ST_AsText(ST_Transform(wkb_geometry, %s))
                FROM ax_flurstueck
                WHERE (gemarkungsnummer = '%s' AND zaehler = '%s' AND %s); """ % (self.curCrs, gem, z, self.nennerQuery(n))

            cur.execute(sql_stmnt)
            resFlst = cur.fetchall()[0][0]
            #print resFlst
            theSelectedGeom = QgsGeometry.fromWkt(resFlst)
            bbox = theSelectedGeom.boundingBox()

            if minx is None:
                minx = bbox.xMinimum()
            if miny is None:
                miny = bbox.yMinimum()

            if bbox.xMinimum() < minx:
                minx = bbox.xMinimum()
            if bbox.yMinimum() < miny:
                miny = bbox.yMinimum()
            if bbox.xMaximum() > maxx:
                maxx = bbox.xMaximum()
            if bbox.yMaximum() > maxy:
                maxy = bbox.yMaximum()

            self.rubberBand.append(QgsRubberBand(canvas, True))
            self.rubberBand[-1].setBorderColor(self.flstHighlightColor)
            self.rubberBand[-1].setFillColor(QtGui.QColor(0,0,0,0))
            self.rubberBand[-1].setWidth(8)
            self.rubberBand[-1].setToGeometry(theSelectedGeom, None)
            count += 1.0
            self.progressBar.setValue(int((count*100)/alle))
        self.selectionExtent = self.bufferExtent(QgsRectangle(QgsPoint(minx, miny), QgsPoint(maxx, maxy)), 0.1)
        self.selectionCenter = QgsPoint(minx + (maxx-minx)*0.5, miny + (maxy-miny)*0.5)


    def bufferExtent(self, rect, buffer_perc=0.1):
        xmin = rect.xMinimum()
        xmax = rect.xMaximum()
        ymin = rect.yMinimum()
        ymax = rect.yMaximum()
        w = xmax-xmin
        h = ymax-ymin
        buf_amount = min(w,h) * buffer_perc * 0.5
        xmin -= buf_amount
        xmax += buf_amount
        ymin -= buf_amount
        ymax += buf_amount
        return QgsRectangle(QgsPoint(xmin, ymin), QgsPoint(xmax, ymax))

    def highlightPoints(self, p_list):
        #input[(wkb,),(wkb,),(wkb,),...]

        canvas = iface.mapCanvas()
        self.deleteRubber(self.rubberHnr)
        self.rubberHnr = []

        for p in p_list:
            #print p[0]
            geom = QgsGeometry().fromWkt(p[0]).buffer(5,40)
            self.rubberHnr.append(QgsRubberBand(canvas, True))
            self.rubberHnr[-1].setBorderColor(QtGui.QColor(0, 0, 0, 0))
            self.rubberHnr[-1].setFillColor(self.hnrHighlightColor)
            self.rubberHnr[-1].setToGeometry(geom, None)

    def deleteRubber(self, rubber_list):
        canvas = iface.mapCanvas()
        alle = float(len(rubber_list))
        count = 0.0
        self.progressBar.setValue(0)
        for r in rubber_list:
            canvas.scene().removeItem(r)
            count += 1.0
            self.progressBar.setValue(int((count * 100) / alle))

    def gotoGeometry(self):
        canvas = iface.mapCanvas()
        canvas.setCenter(self.selectionCenter)
        canvas.refreshAllLayers()

    def zoomGeometry(self):
        canvas = iface.mapCanvas()
        canvas.setExtent(self.selectionExtent)
        canvas.refreshAllLayers()

    def restoreColorSettings(self):
        self.flstHighlightColor = QtGui.QColor().fromRgba(self.settings.value("albeda/flsthighlightcolor", QtGui.QColor(0,0,255,192).rgba()))
        self.setFlstHighlightColor()
        self.hnrHighlightColor = QtGui.QColor().fromRgba(self.settings.value("albeda/hnrhighlightcolor", QtGui.QColor(255,0,0,192).rgba()))
        self.setHnrHighlightColor()
        self.kommFlstColor = QtGui.QColor().fromRgba(self.settings.value("albeda/kommflstcolor", QtGui.QColor(255,255,0,100).rgba()))
        self.setkommFlstColor()
        c = QtGui.QColor(self.settings.value("albeda/tabheadercolor", 0xb0b0b0))
        self.setTableHeaderColor(c)
        c = QtGui.QColor(self.settings.value("albeda/tabrowcolor", 0xffd0c0))
        self.setTableAlteringRowColor(c)
        c = QtGui.QColor(self.settings.value("albeda/tabbgcolor", 0xffffff))
        self.setTableBackgroundColor(c)
        self.alterColors = [self.tableBackgroundColor, self.tableAlteringRowColor]

    #---------------------------------------------Hervorhebung Flurstück
    def defineFlstHighlightColor(self):
        color = QtGui.QColorDialog.getColor(self.flstHighlightColor)
        alpha = self.hs_col_opac_highlight_flst.value()
        r = color.red()
        g = color.green()
        b = color.blue()
        self.flstHighlightColor = QtGui.QColor(r, g, b, alpha)
        self.setFlstHighlightColor()

    def defineFlstHighlightOpacity(self):
        alpha = self.hs_col_opac_highlight_flst.value()
        r = self.flstHighlightColor.red()
        g = self.flstHighlightColor.green()
        b = self.flstHighlightColor.blue()
        self.flstHighlightColor = QtGui.QColor(r, g, b, alpha)
        self.setFlstHighlightColor()

    def setFlstHighlightColor(self):
        self.settings.setValue("albeda/flsthighlightcolor", self.flstHighlightColor.rgba())
        style = 'background-color: rgba(%s, %s, %s, %s)' % self.getRGBA(self.flstHighlightColor)
        self.pb_col_highlight_flst.setStyleSheet(style)
        self.hs_col_opac_highlight_flst.setValue(self.flstHighlightColor.alpha())
        for r in self.rubberBand:
            r.setBorderColor(self.flstHighlightColor)
        iface.mapCanvas().refresh()

    #---------------------------------------------Hervorhebung Hausnummern
    def defineHnrHighlightColor(self):
        color = QtGui.QColorDialog.getColor(self.hnrHighlightColor)
        alpha = self.hs_col_opac_highlight_hnr.value()
        r = color.red()
        g = color.green()
        b = color.blue()
        self.hnrHighlightColor = QtGui.QColor(r, g, b, alpha)
        self.setHnrHighlightColor()

    def defineHnrHighlightOpacity(self):
        alpha = self.hs_col_opac_highlight_hnr.value()
        r = self.hnrHighlightColor.red()
        g = self.hnrHighlightColor.green()
        b = self.hnrHighlightColor.blue()
        self.hnrHighlightColor = QtGui.QColor(r, g, b, alpha)
        self.setHnrHighlightColor()

    def setHnrHighlightColor(self):
        self.settings.setValue("albeda/hnrhighlightcolor", self.hnrHighlightColor.rgba())
        style = 'background-color: rgba(%s, %s, %s, %s)' % self.getRGBA(self.hnrHighlightColor)
        self.pb_col_highlight_hnr.setStyleSheet(style)
        self.hs_col_opac_highlight_hnr.setValue(self.hnrHighlightColor.alpha())
        for r in self.rubberHnr:
            r.setFillColor(self.hnrHighlightColor)
        iface.mapCanvas().refresh()

    #---------------------------------------------kommunaler Grundbesitz
    def defineKommFlstColor(self):
        color = QtGui.QColorDialog.getColor(self.kommFlstColor)
        if color.isValid():
            alpha = self.hs_col_opac_kommflst.value()
            r = color.red()
            g = color.green()
            b = color.blue()
            self.kommFlstColor = QtGui.QColor(r, g, b, alpha)
            self.setkommFlstColor()

    def defineKommFlstOpacity(self):
        alpha = self.hs_col_opac_kommflst.value()
        r = self.kommFlstColor.red()
        g = self.kommFlstColor.green()
        b = self.kommFlstColor.blue()
        self.kommFlstColor = QtGui.QColor(r, g, b, alpha)
        self.setkommFlstColor()

    def setkommFlstColor(self):
        self.settings.setValue("albeda/kommflstcolor", self.kommFlstColor.rgba())
        style = 'background-color: rgba(%s,%s,%s,%s)' % self.getRGBA(self.kommFlstColor)
        self.pb_col_komm_flst.setStyleSheet(style)
        self.hs_col_opac_kommflst.setValue(self.kommFlstColor.alpha())
        if self.kommFlstLayer:
            r = self.kommFlstLayer.rendererV2()
            r.symbol().symbolLayers()[0].setColor(self.kommFlstColor)
            iface.mapCanvas().refreshAllLayers()
            iface.layerTreeView().refreshLayerSymbology(self.kommFlstLayer.id())

    #---------------------------------------------Table Header
    def defineTableHeaderColor(self):
        color = QtGui.QColorDialog.getColor(self.tableHeaderColor)
        self.settings.setValue("albeda/tabheadercolor", color.rgba())
        if color.isValid():
            self.setTableHeaderColor(color)
            for h in self.tableHeaders:
                h.setBackgroundColor(color)

    def setTableHeaderColor(self, c):
        style = 'background-color: %s' % c.name()
        self.tableHeaderColor = c
        self.pb_col_headers.setStyleSheet(style)

    #---------------------------------------------Table Background
    def defineTableBackgroudColor(self):
        color = QtGui.QColorDialog.getColor(self.tableBackgroundColor)
        self.settings.setValue("albeda/tabbgcolor", color.rgba())
        if color.isValid():
            self.setTableBackgroundColor(color)
        self.alterColors = [self.tableBackgroundColor, self.tableAlteringRowColor]

    def setTableBackgroundColor(self, c):
        style = 'background-color: %s' % c.name()
        self.tableBackgroundColor = c
        self.pb_col_tab_bg.setStyleSheet(style)

    #---------------------------------------------Table Altering Color
    def defineTableAlteringRowColor(self):
        color = QtGui.QColorDialog.getColor(self.tableAlteringRowColor)
        self.settings.setValue("albeda/tabalterrowcolor", color.rgba())
        if color.isValid():
            self.setTableAlteringRowColor(color)
        self.alterColors = [self.tableBackgroundColor, self.tableAlteringRowColor]

    def setTableAlteringRowColor(self, c):
        style = 'background-color: %s' % c.name()
        self.tableAlteringRowColor = c
        self.pb_col_alt_flst.setStyleSheet(style)

    #----- Color Helper
    def getRGBA(self, c):
        return (c.red(), c.green(), c.blue(), c.alpha())


    def getCoordinates(self):
        fmt = self.cb_crd_fmt.currentText()
        x, y = (0, 0)
        if fmt == 'metrisch':
            x = 0 if self.x_metr.text() == '' else float(self.x_metr.text().replace(',', '.'))
            y = 0 if self.y_metr.text() == '' else float(self.y_metr.text().replace(',', '.'))
        else:
            dx = 0 if self.x_deg.text() == '' else float(self.x_deg.text().replace(',', '.'))
            dy = 0 if self.y_deg.text() == '' else float(self.y_deg.text().replace(',', '.'))
            mx = 0 if self.x_min.text() == '' else float(self.x_min.text().replace(',', '.'))
            my = 0 if self.y_min.text() == '' else float(self.y_min.text().replace(',', '.'))
            sx = 0 if self.x_sec.text() == '' else float(self.x_sec.text().replace(',', '.'))
            sy = 0 if self.y_sec.text() == '' else float(self.y_sec.text().replace(',', '.'))
            if (dx < -180 or dx > 180) or (dy < -90 or dy > 90) or (mx < 0 or mx >= 60) or (my < 0 or my >= 60) or (sx < 0 or sx >= 60) or (sy < 0 or sy >= 60):
                x = None
                y = None
                mb = QMessageBox()
                mb.setWindowTitle('Hinweis')
                mb.setIcon(QMessageBox.Information)
                mb.setText(u'Wertebereiche für Grad, Minute, Sekunde beachten!')
                mb.setInformativeText(u'Grad (Länge): [-180, 180]\nGrad (Breite): [-90, 90]\nMinute/Sekunde: [0, 60[')
                mb.setStandardButtons(QMessageBox.Ok)
                ret = mb.exec_()
            else:
                x = dx + mx / 60.0 + sx / 3600.0
                y = dy + my / 60.0 + sy / 3600.0

        source_crs = QgsCoordinateReferenceSystem(int(self.cb_epsg.currentText().split(' ')[0]))
        target_crs = self.canvas.mapRenderer().destinationCrs() #QgsCoordinateReferenceSystem(31468)
        if x and y:
            p = QgsGeometry.fromPoint(QgsPoint(x, y))
            p.transform(QgsCoordinateTransform(source_crs, target_crs))
            p = p.asPoint()
        else:
            p = False
        return p

    def qryFlstAtCoords(self):
        p = self.getCoordinates()
        if p:
            #target_crs = self.canvas.mapRenderer().destinationCrs()
            resFlst = self.execSQL("""SELECT gemarkungsnummer, zaehler, COALESCE(nenner, '0'), amtlicheflaeche
                                    FROM ax_flurstueck
                                    WHERE ST_Contains(
                                        ST_Transform(wkb_geometry, %s),
                                        ST_SetSRID(ST_GeomFromText('POINT (%s %s)'), %s)
                                    );""" % (self.curCrs, p.x(), p.y(), self.curCrs))
            #print resFlst
            self.getBestandsAuskunft(resFlst, u'Flurstücksuche an Koordinaten (%s, %s)' % (p.x(), p.y()))

    def blinkCoord(self):
        p = self.getCoordinates()
        if p:
            qg = QgsGeometry.fromPoint(p).buffer(5, 10)
            self.blinkRubber(qg)

    def gotoFlstAtCoords(self):
        p = self.getCoordinates()
        if p:
            iface.mapCanvas().setCenter(p)
            iface.mapCanvas().refreshAllLayers()
            self.blinkCoord()

    def selFlstAtCoords(self):
        p = self.getCoordinates()
        if p:
            layer = QgsMapLayerRegistry.instance().mapLayersByName(self.lineEdit_ax_flst_layer.text())[0]
            layer.setSelectedFeatures([])
            layer.select(QgsRectangle(p, p), True) #2.99: selectByRect()

    def switchCoordinates(self):
        for c in ['metr', 'deg', 'min', 'sec']:
            exec("""x = self.x_%s.text()""" % c)
            exec("""y = self.y_%s.text()""" % c)
            exec("""self.x_%s.setText(y)""" % c)
            exec("""self.y_%s.setText(x)""" % c)

    def findFlurstueckeLive(self):
        zaehler = self.le_zaehler.text()
        zaeSQL = '' if zaehler == '' else "zaehler = '%s' AND " % zaehler

        gem_key = self.cb_gemarkung.currentText()[:4]
        if not gem_key in ('alle', '----', '0000'):
            gem_sql = "gemarkungsnummer = '%s' and " % gem_key
            gem_hint = gem_key
        else:
            gem_sql = ""
            gem_hint = "Alle"

        nenner = self.le_nenner.text()
        if nenner != '':
            nen_sql = self.nennerQuery(nenner)
            nen_hint = nenner
        else:
            nen_sql = "True"
            nen_hint = "Alle"

        display_res_flst = self.execSQL("""SELECT gemarkungsnummer, COUNT(amtlicheflaeche)
                                                FROM ax_flurstueck WHERE (%s%s%s) GROUP BY gemarkungsnummer ORDER BY gemarkungsnummer;""" % (gem_sql, zaeSQL, nen_sql))

        #self.tw_flst_livesearch.clear()
        self.tw_flst_livesearch.setRowCount(len(display_res_flst) + 1)
        self.tw_flst_livesearch.setItem(0, 0, QTableWidgetItem(u'Alle Treffer'))
        self.tw_flst_livesearch.setItem(0, 1, QTableWidgetItem(u''))
        self.tw_flst_livesearch.setCellWidget(0, 3, QCheckBox())
        self.tw_flst_livesearch.cellWidget(0, 3).setTristate(False)
        self.tw_flst_livesearch.cellWidget(0, 3).setChecked(2)
        self.tw_flst_livesearch.cellWidget(0, 3).stateChanged.connect(self.setGmkChecked)
        r = 1
        for g, c in display_res_flst:
            self.tw_flst_livesearch.setItem(r, 0, QTableWidgetItem(u'%s (%s)' % (g, self.gemarkung_ct[g])))
            self.tw_flst_livesearch.setItem(r, 1, QTableWidgetItem(u'%s' % c))
            self.tw_flst_livesearch.setCellWidget(r, 2, QToolButton())
            self.tw_flst_livesearch.cellWidget(r, 2).setToolButtonStyle(1)
            self.tw_flst_livesearch.cellWidget(r, 2).setText(u'¶')
            self.tw_flst_livesearch.cellWidget(r, 2).setStyleSheet(u'font: 8pt "Wingdings";')
            self.tw_flst_livesearch.setCellWidget(r, 3, QCheckBox())
            self.tw_flst_livesearch.cellWidget(r, 3).setChecked(2)
            self.tw_flst_livesearch.cellWidget(r, 3).stateChanged.connect(self.sumFlstCount)
            r += 1
        self.sumFlstCount()

    def setGmkChecked(self):
        s = self.sender()
        for r in range(self.tw_flst_livesearch.rowCount() - 1):
            self.tw_flst_livesearch.cellWidget(r + 1, 3).stateChanged.disconnect(self.sumFlstCount)
            self.tw_flst_livesearch.cellWidget(r + 1, 3).setChecked(s.isChecked())
            self.tw_flst_livesearch.cellWidget(r + 1, 3).stateChanged.connect(self.sumFlstCount)
        self.sumFlstCount()

    def sumFlstCount(self):
        s_bed = 0
        s_ges = 0
        self.tw_flst_livesearch.cellWidget(0, 3).stateChanged.disconnect(self.setGmkChecked)
        for r in range(self.tw_flst_livesearch.rowCount() - 1):
            f = int(self.tw_flst_livesearch.item(r + 1, 1).text())
            if self.tw_flst_livesearch.cellWidget(r + 1, 3).isChecked():
                s_bed += f
            s_ges += f
        self.tw_flst_livesearch.item(0, 1).setText(u'%s / %s' % (s_bed, s_ges))
        if s_bed == 0:
            self.tw_flst_livesearch.cellWidget(0, 3).setChecked(0)
            self.tw_flst_livesearch.item(0, 0).setText(u'Keine Treffer')
        elif s_bed == s_ges:
            self.tw_flst_livesearch.cellWidget(0, 3).setChecked(2)
            self.tw_flst_livesearch.item(0, 0).setText(u'Alle Treffer')
        else:
            self.tw_flst_livesearch.cellWidget(0, 3).setChecked(1)
            ant = float(s_bed) / float(s_ges)
            if ant <= 0.33:
                self.tw_flst_livesearch.item(0, 0).setText(u'Wenige Treffer (%s%%)' % round(ant * 100, 1))
            elif ant > 0.33 and ant <= 0.66:
                self.tw_flst_livesearch.item(0, 0).setText(u'Manche Treffer (%s%%)' % round(ant * 100, 1))
            else:
                self.tw_flst_livesearch.item(0, 0).setText(u'Viele Treffer (%s%%)' % round(ant * 100, 1))
        self.tw_flst_livesearch.cellWidget(0, 3).stateChanged.connect(self.setGmkChecked)

    def queryFlst(self):
        # Flurstücke suchen nach Gemarkung, Zähler, Nenner
        gem_list = []
        for r in range(self.tw_flst_livesearch.rowCount() - 1):
            if self.tw_flst_livesearch.cellWidget(r + 1, 3).isChecked():
                gem_list.append("'%s'" % self.tw_flst_livesearch.item(r + 1, 0).text()[:4])

        gem_list = '(%s)' % ','.join(gem_list)

        gem_sql = "gemarkungsnummer in %s AND " % gem_list

        zaehler = self.le_zaehler.text()
        zae_sql = '' if zaehler == '' else "zaehler = '%s' AND " % zaehler
        zae_hint = zaehler if zaehler != '' else u'Alle'

        nenner = self.le_nenner.text()
        nen_sql = self.nennerQuery(nenner) if nenner != '' else 'True'
        nen_hint = nenner if nenner != '' else u'Alle'

        display_res_flst = self.execSQL("""SELECT gemarkungsnummer, COUNT(amtlicheflaeche)
                                            FROM ax_flurstueck
                                            WHERE (%s%s%s)
                                            GROUP BY gemarkungsnummer
                                            ORDER BY gemarkungsnummer;""" % (gem_sql, zae_sql, nen_sql))

        res_text = u'Zähler: %s Nenner: %s | ' % (zae_hint, nen_hint) + u' | '.join([u'%s (%s): %s Flurstücke' % (g, self.gemarkung_ct[g], n) for g, n in display_res_flst])

        res_flst = self.execSQL("""SELECT gemarkungsnummer, zaehler, COALESCE(nenner, '0'), amtlicheflaeche
                                FROM ax_flurstueck WHERE (%s%s%s);""" % (gem_sql, zae_sql, nen_sql))

        return (res_flst, res_text, (gem_sql, zae_sql, nen_sql))

    def selFlst(self):
        flst, t, q = self.queryFlst()
        self.selectFlstByList(flst)

    def gotoFlst(self):
        flst, t, q = self.queryFlst()
        g, z, n = q
        ext = self.execSQL("""SELECT ST_AsText(ST_SetSRID(ST_Extent(flst.wkb_geometry), %s)) AS extent
                            FROM ax_flurstueck flst WHERE (%s%s%s);""" % (self.curCrs, g, z, n))[0][0]
        self.setExtentFromPg(ext)

    def findFlurstuecke(self):
        flst, t, q = self.queryFlst()
        t = u'Flurstücksuche nach ' + t
        self.getBestandsAuskunft(flst, t)

    def selectFlstByList(self, flstList):
        #Akzeptiert 0 oder NULL für Nenner
        auswahl = []
        layer = QgsMapLayerRegistry.instance().mapLayersByName(self.lineEdit_ax_flst_layer.text())[0]
        # progress Bar init
        alle = layer.dataProvider().featureCount()
        count = 0.0
        self.progressBar.setValue(0)
        for feat in layer.getFeatures():
            gem = feat.attribute('gemarkungsnummer')
            z = feat.attribute('zaehler')
            n = feat.attribute('nenner')
            afl = feat.attribute('amtlicheflaeche')
            if (n == u'0') or (n == NULL):
                if (gem, z, NULL, afl) in flstList or (gem, z, u'0', afl) in flstList:
                    auswahl.append(feat.id())
            else:
                if (gem, z, n, afl) in flstList:
                    auswahl.append(feat.id())
            count += 1.0
            self.progressBar.setValue(int((count*100)/alle))
        layer.setSelectedFeatures(auswahl)


    def getAnliegerFromSelection(self):
        #Anliegerflurstücke zu den selektierten Flurstücken ermitteln

        flst_layer_name = self.lineEdit_ax_flst_layer.text()
        flst_layer = QgsMapLayerRegistry.instance().mapLayersByName(flst_layer_name)

        if len(flst_layer) == 0:
            mb = QMessageBox()
            mb.setWindowTitle('Information')
            mb.setIcon(QMessageBox.Information)
            mb.setText(u'Layer "%s" existiert nicht.' % flst_layer_name)
            mb.setInformativeText(u'Haben Sie die Bezeichnung für den Flurstücklayer geändert? Bitte unter Einstellungen|Datenbank auch die richtige Bezeichnung eintragen!')
            mb.setStandardButtons(QMessageBox.Ok)
            ret = mb.exec_()

        else:
            flst_layer = flst_layer[0]
            flst = flst_layer.selectedFeatures()

            ctflst = len(flst)
            kList = ','.join(["'%s'" % f.attribute('flurstueckskennzeichen') for f in flst])

            #zu Infozwecken, wenn Kartenauswahl nur aus einem Flurstück besteht
            if ctflst == 1:
                f = flst[0]
                gem = f.attribute('gemarkungsnummer')
                z = f.attribute('zaehler')
                n = f.attribute('nenner')

            cur = self.pgConn.cursor()

            SQL = """SELECT DISTINCT b.gemarkungsnummer, b.zaehler, COALESCE(b.nenner, '0') , b.amtlicheflaeche
                 FROM ax_flurstueck as a
                 JOIN ax_flurstueck as b
                 ON ST_Touches((a.wkb_geometry), b.wkb_geometry)
                 WHERE (a.flurstueckskennzeichen IN (%s));""" % kList #(gem,z,n)

            cur.execute(SQL)
            resFlst = cur.fetchall()
            #print resFlst
        
            if self.cb_vorsicht.isChecked():
                #Modus VORSICHTIG
                t = u'Anliegerflurstück'
                if len(resFlst) > 1:
                    t += u'e'
                if ctflst == 1:
                    txt = u'Es existieren %s %s zum Flurstück %s-%s/%s.' % (len(resFlst), t, gem, z, n)
                else:
                    txt = u'Es existieren %s %s zu den ausgewählten Flurstücken.' % (len(resFlst), t)
                info = u'Möchten Sie über das Ergebnis eine Bestandsdatenabfrage durchführen oder in der Karte auswählen?'
                ret = self.handleFlstQueryResult(txt, info)
                if ret == 1:
                    if ctflst == 1:
                        self.getBestandsAuskunft(resFlst, u'Anliegerflurstücke zu %s-%s/%s' % (gem, z, n))
                    else:
                        self.getBestandsAuskunft(resFlst, u'Anliegerflurstücke zu Auswahl')
                elif ret == 0:
                    self.selectFlstByList(resFlst)
            else:
                #Modus MUTIG
                if ctflst == 1:
                    self.getBestandsAuskunft(resFlst, u'Anliegerflurstücke zu %s-%s/%s' % (gem, z, n))
                else:
                    self.getBestandsAuskunft(resFlst, u'Anliegerflurstücke zu Auswahl')

    def makeHnrQuery(self):
        strasse = self.cb_str.currentText()
        cur = self.pgConn.cursor()

        # Gerade
        hnr_even_sql = u'false'
        if self.cb_hnr_even.isChecked():
            hnr_even_sql = u'((substring(a.hausnummer FROM \'[0-9]+\')::int % 2) = 0)'

        # Ungerade
        hnr_odd_sql = u'false'
        if self.cb_hnr_odd.isChecked():
            hnr_odd_sql = u'((substring(a.hausnummer FROM \'[0-9]+\')::int % 2) = 1)'

        # Hausnummernbereich abbilden ------------------------------------------------------
        hnrvon = self.lineEdit_hnrvon.text()
        hnrbis = self.lineEdit_hnrbis.text()

        hnr_man_sql = u'false'

        if hnrbis != '' and hnrvon != '':
            hnr_man_sql = """(
                                          (substring(a.hausnummer FROM '[0-9]+')::int >= %s) AND
                                          (substring(a.hausnummer FROM '[0-9]+')::int <= %s)
                                         )""" % (hnrvon, hnrbis)
        elif hnrbis == '' and hnrvon != '':
            hnr_man_sql = """(substring(a.hausnummer FROM '[0-9]+')::int >= %s)""" % hnrvon

        elif hnrbis != '' and hnrvon == '':
            hnr_man_sql = """(substring(a.hausnummer FROM '[0-9]+')::int <= %s)""" % hnrbi

        # Hausnummernliste abbilden --------------------------------------------------------
        # list may also contain 19a,23c,12g,...
        hnr_list = self.lineEdit_hnrList.text()
        hnr_list_sql = u'false'
        if hnr_list != '':
            hnr_list_sql = """(a.hausnummer IN (%s))""" % (','.join(["'%s'" % x for x in hnr_list.split(',')]))

        # Zusammensetzen -------------------------------------------------------------------
        hnr_man_sql = """(%s OR %s)""" % (hnr_man_sql, hnr_list_sql)

        if self.radioButton_AND.isChecked():
            hnrsql = """((%s OR %s) AND %s)""" % (hnr_even_sql, hnr_odd_sql, hnr_man_sql)
        elif self.radioButton_OR.isChecked():
            hnrsql = """((%s OR %s) OR %s)""" % (hnr_even_sql, hnr_odd_sql, hnr_man_sql)
        elif self.radioButton_XOR.isChecked():
            # xor must be defined as a function boolean xor(boolean, boolean)
            hnrsql = """(xor((%s OR %s), %s))""" % (hnr_even_sql, hnr_odd_sql, hnr_man_sql)

        return hnrsql

    def getFlstFromAdr(self):
        strasse = self.cb_str.currentText()
        cur = self.pgConn.cursor()

        hnrsql = self.makeHnrQuery()

        sql = """SELECT COUNT(a.gml_id) FROM ax_lagebezeichnungmithausnummer AS a
                    JOIN ap_pto AS b ON (a.gml_id = b.dientzurdarstellungvon[1])
                    WHERE (unverschluesselt = '%s' AND %s);""" % (strasse, hnrsql)

        cur.execute(sql)
        ct_hnr = cur.fetchall()[0][0]

        #Flurstücke holen
        sql = """
                SELECT DISTINCT flst.gemarkungsnummer, flst.zaehler, flst.nenner, flst.amtlicheflaeche
                FROM
                    (SELECT gemarkungsnummer, zaehler, COALESCE(nenner, '0') AS nenner, amtlicheflaeche, wkb_geometry
                    FROM ax_flurstueck) flst,
                    (SELECT b.wkb_geometry
                    FROM ax_lagebezeichnungmithausnummer AS a JOIN ap_pto AS b ON (a.gml_id = b.dientzurdarstellungvon[1])
                        WHERE (a.unverschluesselt = '%s' AND %s)) hnr
                WHERE ST_Contains(flst.wkb_geometry, hnr.wkb_geometry);""" % (strasse, hnrsql)
        cur.execute(sql)
        resFlst = cur.fetchall()

        #extent bestimmen
        sql = """
                SELECT ST_AsText(ST_SetSRID(ST_Extent(flst.wkb_geometry), %s)) AS extent
                    FROM ax_flurstueck flst,
                    (SELECT b.wkb_geometry
                    FROM ax_lagebezeichnungmithausnummer AS a JOIN ap_pto AS b ON (a.gml_id = b.dientzurdarstellungvon[1])
                        WHERE (a.unverschluesselt = '%s' AND %s)) hnr
                WHERE ST_Contains(flst.wkb_geometry, hnr.wkb_geometry);""" % (self.curCrs, strasse, hnrsql)
        cur.execute(sql)
        self.setExtentFromPg(cur.fetchall()[0][0])

        if self.cb_vorsicht.isChecked():
            t = u'Flurstück'
            if len(resFlst) > 1:
                t += u'e'
            txt = u'Suche ergab %s Hausnummern für "%s" auf %s Flurstücken (Hinweis: Ggf. mehrere Hausnummern auf einem Flurstück.)' % (ct_hnr, strasse, len(resFlst))
            info = u'Möchten Sie eine Bestandsdatenabfrage durchführen oder das Ergebnis in der Karte auswählen?'
            ret = self.handleFlstQueryResult(txt, info)
            if ret == 1:
                self.getBestandsAuskunft(resFlst, u'Anliegerflurstücke zu "%s", %s Hausnummern' % (strasse, ct_hnr))
            elif ret == 0:
                self.selectFlstByList(resFlst)
        else:
            self.getBestandsAuskunft(resFlst, u'Anliegerflurstücke zu "%s", %s Hausnummern' % (strasse, ct_hnr))

    def showHnr(self):
        strasse = self.cb_str.currentText()

        hnrsql = self.makeHnrQuery()

        # Hausnummern holen
        hnr = self.execSQL("""SELECT ST_AsText(ST_Transform(b.wkb_geometry, %s)) FROM ax_lagebezeichnungmithausnummer AS a
                            JOIN ap_pto AS b ON (a.gml_id = b.dientzurdarstellungvon[1])
                            WHERE (unverschluesselt = '%s' AND %s);""" % (self.curCrs, strasse, hnrsql))
        
        #Extent holen
        ext = self.execSQL("""SELECT ST_AsText(ST_SetSRID(ST_Extent(b.wkb_geometry), %s)) FROM ax_lagebezeichnungmithausnummer AS a
                                    JOIN ap_pto AS b ON (a.gml_id = b.dientzurdarstellungvon[1])
                                    WHERE (unverschluesselt = '%s' AND %s);""" % (self.curCrs, strasse, hnrsql))[0][0]
        self.setExtentFromPg(ext)
        self.highlightPoints(hnr)

    def setExtentFromPg(self, pg_extent):
        try:
            q_extent = self.bufferExtent(QgsGeometry().fromWkt(pg_extent).boundingBox())
            self.canvas.setExtent(q_extent)
            self.canvas.refreshAllLayers()
        except:
            pass

    def setStr(self):
        self.removeHnrRubber()
        self.le_str.clear()
        self.l_str_weg_treffer.setText('#Treffer')

    def geheZuStrasse(self):
        params = {}
        params['str'] = self.cb_str.currentText()
        params['srid'] = self.curCrs
        params['buf'] = 10
        params['h_buf'] = 5

        res = self.execSQL("""SELECT ST_AsText(ST_Extent(ST_Buffer(ST_Transform(wkb_geometry, %(srid)s), %(buf)s)))
                                FROM ax_strassenverkehr
                                WHERE unverschluesselt = '%(str)s'
                            UNION
                                SELECT ST_AsText(ST_Extent(ST_Buffer(ST_Transform(wkb_geometry, %(srid)s), %(buf)s)))
                                FROM ax_weg
                                WHERE unverschluesselt = '%(str)s'""" % params)[0][0]

        self.canvas.setExtent(QgsGeometry.fromWkt(res).boundingBox())
        self.canvas.refreshAllLayers()

    def strHervorheben(self):
        params = {}
        params['str'] = self.cb_str.currentText()
        params['srid'] = self.curCrs
        params['h_buf'] = 5
        # Strasse aufblinken lassen
        res = self.execSQL("""SELECT ST_AsText(ST_Buffer(ST_Union(wkb_geometry), %(h_buf)s))
                                        FROM ax_strassenverkehr
                                        WHERE unverschluesselt = '%(str)s' GROUP BY unverschluesselt
    
                                    UNION
                                        SELECT ST_AsText(ST_Buffer(ST_Union(wkb_geometry), %(h_buf)s))
                                        FROM ax_weg
                                        WHERE unverschluesselt = '%(str)s' GROUP BY unverschluesselt""" % params)[0][0]

        self.blinkRubber(QgsGeometry.fromWkt(res))

    def strasseSelect(self):
        abrv = self.le_str.text()
        hits = []
        for s in self.strassenList:
            if abrv.lower() in s.lower():
                hits.append(s)
        #print hits
        self.l_str_weg_treffer.setText('[%s]' % len(hits))
        if len(hits) == 1:
            self.cb_str.setCurrentIndex(self.cb_str.findText(hits[0]))
            self.le_str.setText(hits[0])
            self.tb_goto_str.setFocus()

    def getFlurstueckeFromMapSelection(self):
        flst_layer_name = self.lineEdit_ax_flst_layer.text()
        flst_layer = QgsMapLayerRegistry.instance().mapLayersByName(flst_layer_name)

        if len(flst_layer) == 0:
            mb = QMessageBox()
            mb.setWindowTitle('Information')
            mb.setIcon(QMessageBox.Information)
            mb.setText(u'Layer "%s" existiert nicht.' % flst_layer_name)
            mb.setInformativeText(
                u'Haben Sie die Bezeichnung für den Flurstücklayer geändert? Bitte unter Einstellungen|Datenbank auch die richtige Bezeichnung eintragen!')
            mb.setStandardButtons(QMessageBox.Ok)
            ret = mb.exec_()

        else:
            flst_layer = flst_layer[0]
            flstList = []
            for f in flst_layer.selectedFeatures():
                gem = f.attribute('gemarkungsnummer')
                z = f.attribute('zaehler')
                n = f.attribute('nenner') or u'0'
                afl = f.attribute('amtlicheflaeche')
                flstList.append((gem,z,n,afl))
            #print flstList
            self.getBestandsAuskunft(flstList, u'Flurstückauswahl in Karte')

    def cleanTabelle(self):
        self.nrow = 0
        self.tableWidget.clearSpans()
        self.tableWidget.setRowCount(0)
        self.tableHeaders = []
        self.removeFlstRubber()

    def cleanTree(self):
        self.treeWidget.clear()
        self.removeFlstRubber()

    def activate3rdRecht(self):
        self.listWidget_eigentum_3rd_recht.setEnabled(self.cb_3rd_beg_recht.isChecked())

    def findeFlstZuEigentuemer(self):
        eigentum_arten = u'(%s)' % ','.join([e.text().split(':')[0] for e in self.listWidget_eigentum_alle.selectedItems()])
        rechte_arten = None
        if self.cb_3rd_beg_recht.isChecked():
            r = self.listWidget_eigentum_3rd_recht.selectedItems()
            if len(r) > 0:
                rechte_arten = u'(%s)' % ','.join([e.text().split(':')[0] for e in r])

        nn = self.lineEdit_nachname.text()
        vn = self.lineEdit_vorname.text()
        if nn != '':
            if vn != '':
                name_query = u"nachnameoderfirma = '%s' AND vorname = '%s'" % (nn, vn)
            else:
                name_query = u"nachnameoderfirma = '%s'" % nn
        else:
            if vn != '':
                name_query = u"vorname = '%s'" % vn
            else:
                name_query = u""

        params = {u'arten':eigentum_arten,
                  u'name':name_query,
                  u'rechte':rechte_arten}

        cur = self.pgConn.cursor()

        if rechte_arten is None:
            sql = u"""SELECT gemarkungsnummer, zaehler, COALESCE(nenner, '0'), amtlicheflaeche FROM ax_flurstueck WHERE istgebucht IN (
                -- Suche über fiktive Buchungsstellen
                SELECT gml_id FROM ax_buchungsstelle
                WHERE gml_id IN (
                    SELECT UNNEST(bst.an) FROM ax_buchungsstelle bst
                    WHERE (bst.an IS NOT NULL AND
                           bst.buchungsart IN %(arten)s AND
                           bst.istbestandteilvon IN (
                                SELECT ax_buchungsblatt.gml_id FROM ax_buchungsblatt
                                WHERE (ax_buchungsblatt.gml_id IN (
                                    SELECT ax_namensnummer.istbestandteilvon FROM ax_namensnummer
                                    WHERE (ax_namensnummer.benennt IN (
                                        SELECT ax_person.gml_id FROM ax_person
                                        WHERE %(name)s)))))))
                UNION ALL
                -- Suche über nicht-fiktive Buchungsstellen
                SELECT gml_id FROM ax_buchungsstelle bst
                WHERE (bst.an IS NULL AND
                       bst.buchungsart IN %(arten)s AND
                       bst.istbestandteilvon IN (
                            SELECT ax_buchungsblatt.gml_id FROM ax_buchungsblatt
                            WHERE (ax_buchungsblatt.gml_id IN (
                                SELECT ax_namensnummer.istbestandteilvon FROM ax_namensnummer
                                WHERE (ax_namensnummer.benennt IN (
                                    SELECT ax_person.gml_id FROM ax_person
                                    WHERE %(name)s)))))));""" % params
        else:
            sql = u"""SELECT gemarkungsnummer, zaehler, COALESCE(nenner, '0'), amtlicheflaeche FROM ax_flurstueck WHERE istgebucht IN (
                            -- Suche über fiktive Buchungsstellen
                            SELECT gml_id FROM ax_buchungsstelle
                            WHERE gml_id IN (
                                SELECT UNNEST(bst.an) FROM ax_buchungsstelle bst
                                WHERE (bst.an IS NOT NULL AND
                                       bst.buchungsart IN %(arten)s AND
                                       bst.istbestandteilvon IN (
                                            SELECT ax_buchungsblatt.gml_id FROM ax_buchungsblatt
                                            WHERE (ax_buchungsblatt.gml_id IN (
                                                SELECT ax_namensnummer.istbestandteilvon FROM ax_namensnummer
                                                WHERE (ax_namensnummer.benennt IN (
                                                    SELECT ax_person.gml_id FROM ax_person
                                                    WHERE %(name)s)))))))
                            UNION ALL
                            -- Suche über nicht-fiktive Buchungsstellen
                            SELECT gml_id FROM ax_buchungsstelle bst
                            WHERE (bst.an IS NULL AND
                                   bst.buchungsart IN %(arten)s AND
                                   bst.istbestandteilvon IN (
                                        SELECT ax_buchungsblatt.gml_id FROM ax_buchungsblatt
                                        WHERE (ax_buchungsblatt.gml_id IN (
                                            SELECT ax_namensnummer.istbestandteilvon FROM ax_namensnummer
                                            WHERE (ax_namensnummer.benennt IN (
                                                SELECT ax_person.gml_id FROM ax_person
                                                WHERE %(name)s))))))) AND

                            istgebucht IN (
                            -- Suche über fiktive Buchungsstellen beg. Rechte
                            SELECT gml_id FROM ax_buchungsstelle
                            WHERE gml_id IN (
                                SELECT UNNEST(bst.an) FROM ax_buchungsstelle bst
                                WHERE (bst.an IS NOT NULL AND
                                       bst.buchungsart IN %(rechte)s AND
                                       bst.istbestandteilvon IN (
                                            SELECT ax_buchungsblatt.gml_id FROM ax_buchungsblatt
                                            WHERE (ax_buchungsblatt.gml_id IN (
                                                SELECT ax_namensnummer.istbestandteilvon FROM ax_namensnummer
                                                WHERE (ax_namensnummer.benennt IN (
                                                    SELECT ax_person.gml_id FROM ax_person
                                                    WHERE NOT(%(name)s)))))))));""" % params
        #print sql
        cur.execute(sql)
        resFlst = cur.fetchall()

        if self.cb_vorsicht.isChecked():
            # Modus VORSICHTIG
            t = u'Flurstück'
            v = u'wurde'
            if len(resFlst) > 1:
                t += u'e'
                v += u'n'
            txt = u'Es %s %s %s gefunden.' % (v, len(resFlst), t)
            info = u"""Möchten Sie über das Ergebnis eine Bestandsdatenabfrage durchführen oder in der Karte auswählen?\n\nHinweis: Beide Aktionen werden protokolliert!"""
            ret = self.handleFlstQueryResult(txt, info)
            if ret == 1:
                self.getBestandsAuskunft(resFlst, u'Eigentümerabfrage')
            elif ret == 0:
                self.selectFlstByList(resFlst)
        else:
            # Modus MUTIG
            if ctflst == 1:
                self.getBestandsAuskunft(resFlst, u'Anliegerflurstücke zu %s-%s/%s' % (gem, z, n))
            else:
                self.getBestandsAuskunft(resFlst, u'Anliegerflurstücke zu Auswahl')

    def getBestandsAuskunft(self, flstListe, artDesZugriffs):
        try:
            now = datetime.datetime.now()
            headline = u'%s (%02d.%02d.%d, %02d:%02d:%02d, %s Flurstücke)' % (artDesZugriffs, now.day, now.month, now.year, now.hour, now.minute, now.second, len(flstListe))

            #************************************ Aufräumen falls gewünscht
            if self.cb_clean_tab.isChecked():
                self.cleanTabelle()

            if self.cb_clean_tree.isChecked():
                self.cleanTree()

            treeItemRoot = QtGui.QTreeWidgetItem([headline])

            #************************************ Überschriften / Kopfzeilen
            if self.cb_query_headline.isChecked():
                self.addTabellenZeile(1)
                self.tableWidget.setSpan(self.nrow,0,1,16)
                self.tableHeaders.append(QtGui.QTableWidgetItem(headline))
                self.tableWidget.setItem(self.nrow,0,self.tableHeaders[-1])
                if self.cb_highlight_headline.isChecked():
                    self.tableHeaders[-1].setBackgroundColor(self.tableHeaderColor)
                else:
                    self.tableHeaders[-1].setBackgroundColor(self.tableBackgroundColor)


            #************************************ progressBar initialisieren
            alle = float(len(flstListe))
            count = 0.0
            self.progressBar.setValue(0)

            #************************************ Flurstücke abarbeiten
            colorIndex = 1
            flstListe.sort()
            for f in flstListe:
                colorIndex = 1 - colorIndex
                self.addTabellenZeile(colorIndex)

                #print f
                gem, z, n, afl = f
                flst_kennz = self.execSQL("""SELECT flurstueckskennzeichen FROM ax_flurstueck
                                            WHERE (gemarkungsnummer = '%s' AND zaehler = '%s' AND %s)""" % (gem, z, self.nennerQuery(n)))[0][0]
                #print flst_kennz
                #print f
                flst = u'%s-%s/%s' % (gem,z,n)
                #Gibt Probleme mit Flurstueckhighlighting
                #treeFlurstueck = QtGui.QTreeWidgetItem([u'%s [%s]' % (flst, flst_kennz)])
                treeFlurstueck = QtGui.QTreeWidgetItem([flst])
                treeItemRoot.addChild(treeFlurstueck)

                #Eintrag Tabelle Flurstücknummer
                self.tableWidget.item(self.nrow, 0).setText(flst)
                self.tableWidget.item(self.nrow, 1).setText(flst_kennz)
                self.tableWidget.item(self.nrow, 4).setText(u'%s' % afl)

                #'an' ist hier per definitionem immer null!!!
                res = self.execSQL("""SELECT gml_id, istbestandteilvon, buchungsart, laufendenummer, zaehler, COALESCE(nenner, '0'), an
                               FROM ax_buchungsstelle
                               WHERE gml_id IN
                                   (SELECT istgebucht
                                   FROM ax_flurstueck
                                   WHERE (gemarkungsnummer = '%s' AND zaehler = '%s' AND %s));""" % (gem, z, self.nennerQuery(n)))

                for r in res:
                    gml_id_bst, istbestandteilvon, buchungsart, laufendenummer, zaehler, nenner, an = r
                    anteil = self.cleanZaehlerNenner((zaehler, nenner))
                    buchungsblattkennzeichen,\
                    blattart,\
                    gml_id_bbl = self.execSQL("""SELECT buchungsblattkennzeichen, blattart, gml_id FROM ax_buchungsblatt WHERE gml_id = '%s'""" % istbestandteilvon)[0]
                    treeBuSt = QtGui.QTreeWidgetItem([u'Buchungsstelle LfdNr. %s, Art: %s (%s), Anteil: %s, Bestandteil von Buchungsblatt: %s, Art: %s (%s)' % (laufendenummer, buchungsart, self.buch_art[buchungsart], anteil, buchungsblattkennzeichen, blattart, self.kt_blattart[int(blattart)])])
                    treeFlurstueck.addChild(treeBuSt)
                    #print"#Eintrag Tabelle"
                    #Falls 'Tabelle komplett befüllen' angehakt:
                    if self.cb_fill_each_line.isChecked():
                        self.tableWidget.item(self.nrow, 0).setText(flst)
                        self.tableWidget.item(self.nrow, 1).setText(flst_kennz)

                        self.tableWidget.item(self.nrow, 4).setText(u'%s' % afl)

                    self.tableWidget.item(self.nrow, 2).setText(laufendenummer)
                    self.tableWidget.item(self.nrow, 3).setText(anteil)
                    self.tableWidget.item(self.nrow, 5).setText(buchungsblattkennzeichen)
                    self.tableWidget.item(self.nrow, 6).setText(u'%s (%s)'% (buchungsart, self.buch_art[buchungsart]))

                    #-------------------------------------------
                    # Einfach: über Buchungsblatt
                    #-------------------------------------------
                    res_nnr = self.execSQL("""SELECT gml_id, benennt, artderrechtsgemeinschaft, eigentuemerart, laufendenummernachdin1421, nummer
                                     FROM ax_namensnummer
                                     WHERE istbestandteilvon = '%s'""" % istbestandteilvon)
                    if len(res_nnr) == 0:
                        treeNNrPers = QtGui.QTreeWidgetItem([u'Keine Eigentümerinformation via Buchungsblatt'])
                    ct = 0
                    for nnr in res_nnr:
                        if ct > 0:
                            self.addTabellenZeile(colorIndex)
                        gml_id, benennt, artderrechtsgemeinschaft, eigentuemerart, laufendenummernachdin1421, nummer = nnr
                        
                        if benennt is not None:
                            anrede,\
                            vorname,\
                            nachnameoderfirma,\
                            gebdat,\
                            agrad,\
                            hat = self.execSQL("""SELECT anrede, vorname, nachnameoderfirma, geburtsdatum, akademischergrad, hat FROM ax_person WHERE gml_id = '%s'""" % benennt)[0]
                        else:
                            anrede, vorname, nachnameoderfirma, gebdat, agrad, hat = (None, None, 'n.v.', 'n.v.', '-', [])
                        
                        treeNNrPers = QtGui.QTreeWidgetItem([u'Nummer: %s, LfdNr. DIN 1421: %s, %s, %s - Person/Fa.: %s' % (nummer, laufendenummernachdin1421, self.cleanEigent(eigentuemerart), self.cleanRG(artderrechtsgemeinschaft), self.cleanPers(anrede, vorname, nachnameoderfirma))])

                        if self.cb_fill_each_line.isChecked():
                            self.tableWidget.item(self.nrow, 0).setText(flst)
                            self.tableWidget.item(self.nrow, 1).setText(flst_kennz)

                            self.tableWidget.item(self.nrow, 4).setText(u'%s' % afl)
                            self.tableWidget.item(self.nrow, 2).setText(laufendenummer)
                            self.tableWidget.item(self.nrow, 3).setText(anteil)
                            self.tableWidget.item(self.nrow, 5).setText(buchungsblattkennzeichen)
                            self.tableWidget.item(self.nrow, 6).setText(u'%s (%s)' % (buchungsart, self.buch_art[buchungsart]))

                        self.tableWidget.item(self.nrow, 7).setText(laufendenummernachdin1421)
                        if not anrede == None:
                            self.tableWidget.item(self.nrow, 8).setText(self.kt_anrede[anrede])
                        self.tableWidget.item(self.nrow, 9).setText(agrad)
                        self.tableWidget.item(self.nrow, 10).setText(nachnameoderfirma)
                        self.tableWidget.item(self.nrow, 11).setText(vorname)
                        self.tableWidget.item(self.nrow, 12).setText(self.deDate(gebdat))

                        if hat != None:
                            if len(hat) > 0:  # ax_person 'hat' ax_anschrift
                                self.makeAdressEintrag(treeNNrPers, hat[0])
                                if len(hat) > 1:
                                    for adr_id in hat[1:]:
                                        self.addTabellenZeile(colorIndex)
                                        self.makeAdressEintrag(treeNNrPers, adr_id)
                        ct += 1

                        treeBuSt.addChild(treeNNrPers)
                        
                    #------------------------------------------------------------------
                    # nicht ganz so einfach: über fiktive Buchungsblätter (5000)
                    #------------------------------------------------------------------
                    self.findBegRechte(flst, afl, gml_id_bst, treeBuSt, colorIndex, flst_kennz)

                count += 1.0
                self.progressBar.setValue(int((count*100)/alle))

            # Optimale Breite setzen...
            self.tableWidget.horizontalHeader().setResizeMode(QtGui.QHeaderView.ResizeToContents)
            # ... und wieder dem Nutzer überlassen.
            #self.tableWidget.horizontalHeader().setResizeMode(QtGui.QHeaderView.Interactive)
            
            self.treeWidget.addTopLevelItem(treeItemRoot)

        except:
            e = sys.exc_info()[0]
            print "Error: %s" % e
            traceback.print_exc()

    def findBegRechte(self, flst, afl, gml_id_an, parent_tree_node, cix, flst_kennz):
        via_an = self.execSQL("""SELECT gml_id, istbestandteilvon, buchungsart, laufendenummer, zaehler, nenner FROM ax_buchungsstelle WHERE '%s' = ANY(an)""" % gml_id_an)
        for v in via_an:
            self.addTabellenZeile(cix)
            gml_id, istbestandteilvon_an, buchungsart, laufendenummer, zaehler, nenner = v

            anteil = self.cleanZaehlerNenner((zaehler, nenner))
            buchungsblattkennzeichen,\
            blattart,\
            gml_id_bbl = self.execSQL("""SELECT buchungsblattkennzeichen, blattart, gml_id FROM ax_buchungsblatt WHERE gml_id = '%s'""" % istbestandteilvon_an)[0]

            treeBuStBegR = QtGui.QTreeWidgetItem([
                                                     u'Beg. Recht: Buchungsstelle LfdNr. %s, Art: %s (%s), Anteil: %s, Bestandteil von Buchungsblatt: %s, Art: %s (%s)' % (
                                                     laufendenummer, buchungsart, self.buch_art[buchungsart], anteil,
                                                     buchungsblattkennzeichen, blattart,
                                                     self.kt_blattart[int(blattart)])])
            parent_tree_node.addChild(treeBuStBegR)

            self.tableWidget.item(self.nrow, 2).setText(laufendenummer)
            self.tableWidget.item(self.nrow, 3).setText(anteil)
            self.tableWidget.item(self.nrow, 5).setText(buchungsblattkennzeichen)
            self.tableWidget.item(self.nrow, 6).setText(u'%s (%s)' % (buchungsart, self.buch_art[buchungsart]))

            res_nnr = self.execSQL("""SELECT gml_id, benennt, artderrechtsgemeinschaft, eigentuemerart, laufendenummernachdin1421, nummer
                                                FROM ax_namensnummer
                                                WHERE istbestandteilvon = '%s'""" % istbestandteilvon_an)
            ct = 0
            for nnr in res_nnr:
                if ct > 0:
                    self.addTabellenZeile(cix)
                gml_id, benennt, artderrechtsgemeinschaft, eigentuemerart, laufendenummernachdin1421, nummer = nnr

                if benennt is not None:
                    anrede, vorname, nachnameoderfirma, gebdat, agrad, hat = self.execSQL("""SELECT anrede, vorname, nachnameoderfirma, geburtsdatum, akademischergrad, hat FROM ax_person WHERE gml_id = '%s'""" % benennt)[0]
                else:
                    anrede, vorname, nachnameoderfirma, gebdat, agrad, hat = (None, None, 'n.v.', 'n.v.', '-', [])

                treeNNrPersBegR = QtGui.QTreeWidgetItem([u'Nummer: %s, LfdNr. DIN 1421: %s, %s, %s - Person/Fa.: %s' % (
                nummer, laufendenummernachdin1421, self.cleanEigent(eigentuemerart),
                self.cleanRG(artderrechtsgemeinschaft), self.cleanPers(anrede, vorname, nachnameoderfirma))])

                if self.cb_fill_each_line.isChecked():
                    self.tableWidget.item(self.nrow, 0).setText(flst)
                    self.tableWidget.item(self.nrow, 1).setText(flst_kennz)

                    self.tableWidget.item(self.nrow, 4).setText(u'%s' % afl)
                    self.tableWidget.item(self.nrow, 2).setText(laufendenummer)
                    self.tableWidget.item(self.nrow, 3).setText(anteil)
                    self.tableWidget.item(self.nrow, 5).setText(buchungsblattkennzeichen)
                    self.tableWidget.item(self.nrow, 6).setText(u'%s (%s)' % (buchungsart, self.buch_art[buchungsart]))

                self.tableWidget.item(self.nrow, 7).setText(laufendenummernachdin1421)
                if not anrede == None:
                    self.tableWidget.item(self.nrow, 8).setText(self.kt_anrede[anrede])
                self.tableWidget.item(self.nrow, 9).setText(agrad)
                self.tableWidget.item(self.nrow, 10).setText(nachnameoderfirma)
                self.tableWidget.item(self.nrow, 11).setText(vorname)
                self.tableWidget.item(self.nrow, 12).setText(self.deDate(gebdat))

                if hat != None:
                    if len(hat) > 0:  # ax_person 'hat' ax_anschrift
                        self.makeAdressEintrag(treeNNrPersBegR, hat[0])
                        if len(hat) > 1:
                            for adr_id in hat[1:]:
                                self.addTabellenZeile(cix)
                                self.makeAdressEintrag(treeNNrPersBegR, adr_id)
                ct += 1
                treeBuStBegR.addChild(treeNNrPersBegR)

            test_bst = self.execSQL(u"""SELECT gml_id FROM ax_buchungsstelle WHERE '%s' = ANY(an)""" % gml_id)
            if len(test_bst) > 0:
                self.findBegRechte(flst, afl, gml_id, treeBuStBegR, cix)

    def makeAdressEintrag(self, treeNNrPers, hat_adr):
        res_adr = self.execSQL(u"""SELECT postleitzahlpostzustellung, ort_post, ortsteil, strasse, hausnummer FROM ax_anschrift WHERE gml_id = '%s'""" % hat_adr)
        treeAnschr = QtGui.QTreeWidgetItem([u'%s %s, %s, %s %s' % res_adr[0]])
        treeNNrPers.addChild(treeAnschr)
        plz, ort, ortsteil, strasse, hnr = res_adr[0]
        self.tableWidget.item(self.nrow, 13).setText(u'%s %s' % (strasse, hnr))
        self.tableWidget.item(self.nrow, 14).setText(u'%s %s' % (plz, ort))

    def addTabellenZeile(self, altCol):
        self.tableWidget.setRowCount(self.tableWidget.rowCount() + 1)
        self.nrow = self.tableWidget.rowCount() - 1
        for c in range(self.tableWidget.columnCount()):
            i = QtGui.QTableWidgetItem(u'')
            self.tableWidget.setItem(self.nrow, c, i)
            i.setBackgroundColor(self.alterColors[altCol])
        return True
            
    def cleanZaehlerNenner(self, zn):
        # Eingabe: Tupel von dem nicht bekannt ist ob (None, None) oder (float, float)
        z, n = zn
        if z is not None and z == int(z):
            z = int(z)
        if n is not None and n == int(n):
            n = int(n)
        return ('%s/%s' % (z,n)).replace('.',',').replace('None','-')

    def deDate(self, isodate):
        if isodate == 'n.v.' or isodate is None:
            return isodate
        else:
            y,m,d = isodate.split('-')
            return '%s.%s.%s' % (d, m, y)

    def cleanRG(self, rg):
        if rg is not None:
            artRG = u'Rechtsgemeinschaft: %s (%s)' % (rg, self.rechtsgemeinschaft_art[rg])
        else:
            artRG = u'RG n.a.'
        return artRG

    def cleanEigent(self, eig):
        if eig is not None:
            artEigent = u'Art des Eigentümers: %s (%s)' % (eig, self.eigentuemer_art[eig])
        else:
            artEigent = u'Art des Eigentümers n.a.'
        return artEigent

    def cleanPers(self, anr, vn, nn):
        if anr is not None:
            pers = u'%s %s, %s' % (self.kt_anrede[anr], vn, nn)
        else:
            pers = u'%s' % nn
        return pers

    def nennerQuery(self, n):
        #nötig, weil nenner auch NULL sein kann
        n_sql = ''
        if n == '0' or n == 'NULL' or not n:
            n_sql = "(nenner = '0' or nenner IS NULL)"
        else:
            n_sql = "nenner = '%s'" % n
        return n_sql


    #def findeEigentuemer(self):
    #    for n in range(self.listWidget_eigentum_auswahl.count()):
    #        print self.listWidget_eigentum_auswahl.item(n).text().split(':')


    def removeFlstRubber(self):
        for r in self.rubberBand:
            r.reset()
        self.rubberBand = []

    def removeHnrRubber(self):
        for r in self.rubberHnr:
            r.reset()
        self.rubberHnr = []

    def blinkRubber(self, qgeom):
        self.rubberCoordTemp.append(QgsRubberBand(self.canvas, True))
        self.rubberCoordTemp[-1].setBorderColor(QColor(255, 255, 255, 0))
        self.rubberCoordTemp[-1].setFillColor(QtGui.QColor(0, 0, 255, 128))
        self.rubberCoordTemp[-1].setWidth(0)
        self.rubberCoordTemp[-1].setToGeometry(qgeom, None)
        # rubber erzeugen
        QTimer.singleShot(1500, self.removeRubberCoordTemp)

    def removeRubberCoordTemp(self):
        for r in self.rubberCoordTemp:
            iface.mapCanvas().scene().removeItem(r)
        self.rubberCoordTemp = []

    def closeEvent(self, event):
        self.removeFlstRubber()
        self.removeHnrRubber()
        self.closingPlugin.emit()
        event.accept()

    def handleFlstQueryResult(self, txt, infotxt):
        msgBox = QtGui.QMessageBox()
        msgBox.setWindowTitle(u'Suchergebnis')
        msgBox.setText(txt)
        msgBox.setInformativeText(infotxt)
        auswahlButton = msgBox.addButton(u'Auswählen', QtGui.QMessageBox.ActionRole)
        abfrageButton = msgBox.addButton(u'Abfrage', QtGui.QMessageBox.ActionRole)
        cancelButton = msgBox.addButton(u'Abbrechen', QtGui.QMessageBox.ActionRole)
        msgBox.setDefaultButton(cancelButton)
        msgBox.setIcon(QtGui.QMessageBox.Information)
        return msgBox.exec_()

    def exportTable(self):
        filename = unicode(QtGui.QFileDialog.getSaveFileName(self, 'Speichern unter...', None,'Tabellen (*.xls *.csv)'))
        if filename[-3:] == u'xls':
            mappe = xlwt.Workbook()
            blatt = mappe.add_sheet('ALBeDA Export')
            for col in range(self.tableWidget.columnCount()):
                #spaltenköpe, formatierungen
                h = self.tableWidget.horizontalHeaderItem(col)
                blatt.write(0, col, h.text())
                for row in range(self.tableWidget.rowCount()):
                    it = self.tableWidget.item(row, col)
                    text = u''
                    if it is not None:
                        text = unicode(it.text())
                    blatt.write(row+1, col, text)
            mappe.save(filename)
        elif filename[-3:] == u'csv':
            with codecs.open(filename, 'wb', encoding='utf-8') as csvfile:
                #csvwriter = csv.writer(csvfile, delimiter=self.le_csv_col_sep.text()[0], quotechar=self.le_csv_text_quote.text()[0], quoting=csv.QUOTE_MINIMAL)
                #csvwriter = csv.writer(csvfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)

                #header names
                csvfile.write(u'%s\n' % self.le_csv_col_sep.text()[0].join([self.tableWidget.horizontalHeaderItem(col).text() for col in range(self.tableWidget.columnCount())]))
                for row in range(self.tableWidget.rowCount()):
                    csvfile.write(u'%s\n' % self.le_csv_col_sep.text()[0].join([self.tableWidget.item(row, col).text() for col in range(self.tableWidget.columnCount())]))
                csvfile.close()

    def keepCurrentTab(self):
        s = self.sender()
        sn = s.objectName()
        self.settings.setValue('albeda/tabs/%s' % sn, s.currentIndex())

    def getPluginVersion(self):
        user = QgsExpressionContextUtils.globalScope().variable('user_account_name')
        #look in users home directory
        v = ''
        for x in findPlugins('C:\\Users\\%s\\.qgis2\python\plugins' % user):
            if x[0] == 'ALBeDa':
                v = x[1].get('general', 'version')
        if v == '':
            try:
                for x in findPlugins(os.environ['QGIS_PLUGINPATH']):
                    if x[0] == 'ALBeDa':
                        v = x[1].get('general', 'version')
            except:
                raise('QGIS_PLUGINPATH not set.')
        return v

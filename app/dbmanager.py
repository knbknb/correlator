#!/usr/bin/env python

## For Mac-OSX
#/usr/bin/env pythonw

import platform
platform_name = platform.uname()

import wx 
import wx.gizmos as gizmos
from wx.lib import plot
import random, sys, os, re, time, ConfigParser, string
from datetime import datetime
import xml.sax

from importManager import py_correlator

import dialog
import tabularImport
import xml_handler
from model import * # brgtodo 4/24/2014: Remove import *

def opj(path):
	"""Convert paths to the platform-specific separator"""
	return apply(os.path.join, tuple(path.split('/')))


FormatDict = {"Text":0, "CSV":1, "XML":2}

# list of a site node's immediate non-measurement children 
STD_SITE_NODES = ["Saved Tables", "Downhole Log Data", "Stratigraphy", "Age Models", "Image Data", "Section Summary"]

class DataFrame(wx.Panel):
	def __init__(self, parent):
		wx.Panel.__init__(self, parent, -1)

		self.parent = parent
		self.selectedCol = -1
		self.paths = ""
		self.EditRow = -1
		self.selectedIdx = None 
		self.firstIdx = None 
		self.currentIdx = [] 
		self.propertyIdx = None
		self.title = ""
		self.importType = None
		self.importLabel = [] 
		self.logHole = "" 
		self.cullData = [] 
		self.selectBackup = None
		self.selectedDataType = ""
		self.selectedDepthType = ""
		self.SetBackgroundColour(wx.Colour(255, 255, 255))
		self.parser = xml.sax.make_parser()
		self.handler = xml_handler.XMLHandler()
		self.parser.setContentHandler(self.handler)

		self.sideNote = wx.Notebook(self, -1, style=wx.NB_TOP)
		self.sideNote.SetBackgroundColour(wx.Colour(255, 255, 255))
		
		self.pathPanel = wx.Panel(self, -1)
		self.PathTxt = wx.TextCtrl(self.pathPanel, -1, "Path : " + self.parent.DBPath)
		self.PathTxt.SetEditable(False)

		self.importbtn = wx.Button(self.pathPanel, -1, "Import")
		self.Bind(wx.EVT_BUTTON, self.OnIMPORT, self.importbtn)
		self.importbtn.Enable(False)

		# 1/8/2014 brgtodo: What is the point of the Dismiss button??? It just hides the data manager, f'nality
		# more usefully implemented in the "Go to Display/Data Manager" button in the toolbar. Why would a user
		# want to just hide the Data Manager?  Strong candidate for removal.
		self.okbtn = wx.Button(self.pathPanel, -1, "Dismiss")
		self.Bind(wx.EVT_BUTTON, self.OnDISMISS, self.okbtn)

		pathPanelSizer = wx.BoxSizer(wx.HORIZONTAL)
		pathPanelSizer.Add(self.PathTxt, 1, wx.LEFT | wx.RIGHT, 5)
		pathPanelSizer.Add(self.importbtn, 0, wx.LEFT | wx.RIGHT, 5)
		pathPanelSizer.Add(self.okbtn, 0, wx.LEFT | wx.RIGHT, 5)
		self.pathPanel.SetSizer(pathPanelSizer)

		self.SetSizer(wx.BoxSizer(wx.VERTICAL))
		self.GetSizer().Add(self.sideNote, 1, wx.EXPAND)
		self.GetSizer().Add(self.pathPanel, 0, wx.EXPAND | wx.BOTTOM, 5)

		self.treeListPanel = wx.Panel(self.sideNote, -1)
		#self.treeListPanel = wx.Panel(self, -1)

		self.tree = gizmos.TreeListCtrl(self.treeListPanel, -1, style = wx.TR_DEFAULT_STYLE | wx.TR_FULL_ROW_HIGHLIGHT)
		self.tree.AddColumn(" ")
		self.tree.SetColumnWidth(0, 200)
		self.tree.AddColumn("Data")
		self.tree.SetColumnWidth(1, 200)
		self.tree.AddColumn("Enable")
		self.tree.AddColumn("Decimate")
		self.tree.AddColumn("Min")
		self.tree.AddColumn("Max")
		self.tree.AddColumn("Updated Time")
		self.tree.SetColumnWidth(6, 150)
		self.tree.AddColumn("By Whom")
		self.tree.AddColumn("File Output Name")
		self.tree.SetColumnWidth(8, 250)
		self.tree.AddColumn("Input Source File")
		self.tree.SetColumnWidth(9, 650)
		self.tree.AddColumn("Path")
		self.tree.SetColumnWidth(10, 150)
		self.tree.AddColumn("Data Index")
		self.tree.AddColumn("Smooth")
		self.tree.SetColumnWidth(12, 250)
		self.tree.AddColumn("Y")

		self.tree.SetMainColumn(0)
		self.root = self.tree.AddRoot("Root")
		self.tree.Expand(self.root)

		self.treeListPanel.SetSizer(wx.BoxSizer(wx.VERTICAL))
		self.treeListPanel.GetSizer().Add(self.tree, 1, wx.EXPAND)
		self.sideNote.AddPage(self.treeListPanel, 'Data List')
		self.tree.GetMainWindow().Bind(wx.EVT_RIGHT_DOWN, self.SelectTREE)

		#self.dbPanelParent = wx.Panel(self.sideNote, -1)
		#self.dbPanelParent.SetSizer(wx.BoxSizer(wx.VERTICAL))

# 		self.dbPanel = wx.ScrolledWindow(self.dbPanelParent, -1)
# 		self.dbPanel.SetScrollbars(5, 5, 1200, 800) #1/6/2014 brgtodo
# 		self.dbPanel.SetSizer(wx.BoxSizer(wx.VERTICAL))
# 		self.dbPanel.SetBackgroundColour('white')

		# 1/6/2014 brg: On Mac, only left half of vertical scrollbar appears. Seems the ScrolledWindow
		# is too wide for the parent window. Add to a Panel so we can use a fudged border on the right
		# to make things look correct.
		#self.dbPanelParent.GetSizer().Add(self.dbPanel, 1, wx.EXPAND | wx.RIGHT, 9)
		#self.sideNote.AddPage(self.dbPanelParent, 'Data List v2')

		self.dataPanel = dialog.CoreSheet(self.sideNote, 120, 100)
		self.sideNote.AddPage(self.dataPanel, 'Generic Data')
		self.Bind(wx.grid.EVT_GRID_LABEL_LEFT_CLICK, self.OnSELECTCELL, self.dataPanel)
		font = self.dataPanel.GetFont()
		font.SetFamily(wx.FONTFAMILY_ROMAN)
		self.dataPanel.SetFont(font)
		
		self.filePanel = wx.Panel(self.sideNote, -1)
		self.fileText = wx.TextCtrl(self.filePanel, -1, "", style=wx.TE_MULTILINE|wx.TE_READONLY|wx.VSCROLL|wx.TE_WORDWRAP)
		self.fileText.SetEditable(False)
		self.fileText.SetFont(wx.Font(14,wx.FONTFAMILY_TELETYPE,wx.FONTSTYLE_NORMAL,wx.FONTWEIGHT_NORMAL)) # fixed-width font
		fpsizer = wx.BoxSizer(wx.VERTICAL)
		fpsizer.Add(self.fileText, 1, wx.EXPAND)
		self.filePanel.SetSizer(fpsizer)
		self.sideNote.AddPage(self.filePanel, 'Data File')

		self.dataPanel.SetColLabelValue(0, "Data Type")
		self.dataPanel.SetColSize(0, 150)
		for i in range(1, 39) :
			self.dataPanel.SetColLabelValue(i, "?")

		self.initialize = False

		self.repCount = 0
		wx.EVT_CLOSE(self, self.OnHide)

	def OnHide(self,event):
		self.Show(False)
		self.parent.midata.Check(False)
		
	def OnSecSummMenu(self, event):
		opId = event.GetId()
		if opId == 1:
			self.ImportSectionSummary()
		elif opId == 2: # View File
			filepath = self.parent.DBPath + 'db/' + self.GetSelectedSite() + '/' + self.tree.GetItemText(self.selectedIdx, 1)
			self.fileText.Clear()
			self.fileText.LoadFile(filepath)
			self.sideNote.SetSelection(2)
		elif opId == 3: # Delete
			secsummname = self.tree.GetItemText(self.selectedIdx, 1)
			ret = self.parent.OnShowMessage("Information", "Are you sure you want to delete {}?".format(secsummname), 2)
			if ret == wx.ID_OK:
				filepath = self.parent.DBPath + 'db/' + self.GetSelectedSite() + '/' + secsummname
				os.remove(filepath)
				self.tree.SetItemText(self.selectedIdx, "", 1)
				self.OnUPDATE_DB_FILE(self.GetSelectedSite(), self.tree.GetItemParent(self.selectedIdx))

	# handles all of the many many many right-click commands in Data Manager
	def OnPOPMENU(self, event):
		opId = event.GetId()
		self.currentIdx = self.tree.GetSelections()
		if opId == 1 :	# LOAD CORE
			self.OnLOAD()
		elif opId == 2 : # VIEW FILE
			filename = self.tree.GetItemText(self.selectedIdx, 8)
			if filename != "" :
				filename = self.parent.DBPath + 'db/' + self.tree.GetItemText(self.selectedIdx, 10) + filename
				self.fileText.Clear()
				self.fileText.LoadFile(filename)
				self.sideNote.SetSelection(2)
		elif opId == 3 : # EDIT CORE
			self.importType = "CORE"
			self.importLabel = []
			self.selectedDataType = ""
			self.selectedDepthType = ""
			self.OnEDIT()
		elif opId == 4 :
			# IMPORT AFFINE TABLE
			self.OnIMPORT_TABLE("Affine")
		elif opId == 5 :
			# OPEN CORE
			self.importType = "CORE"
			self.selectedDataType = ""
			self.selectedDepthType = ""
			self.OnOPEN()
		elif opId == 6 :
			# DELETE 
			self.OnDELETE()
		elif opId == 7 :
			self.OnUPDATE()
		elif opId == 9 :
			# IMPORT CULL TABLE
			self.OnIMPORT_CULLTABLE(False)
		elif opId == 10 :
			# DISABLE
			self.tree.SetItemText(self.selectedIdx, 'Disable', 2)
			self.tree.SetItemTextColour(self.selectedIdx, wx.RED)
			item = self.tree.GetItemParent(self.selectedIdx)
			item = self.tree.GetItemParent(item)
			self.OnUPDATE_DB_FILE(self.tree.GetItemText(item, 0), item)
		elif opId == 11 :
			# ENABLE
			self.tree.SetItemText(self.selectedIdx, 'Enable', 2)
			self.tree.SetItemTextColour(self.selectedIdx, wx.BLUE)
			item = self.tree.GetItemParent(self.selectedIdx)
			item = self.tree.GetItemParent(item)
			self.OnUPDATE_DB_FILE(self.tree.GetItemText(item, 0), item)
		elif opId == 12 :
			# IMPORT LOG 
			self.importType = "LOG"
			self.selectedDataType = ""
			self.selectedDepthType = ""
			self.OnOPEN_LOG()
		elif opId == 13 :
			# EDIT LOG
			self.importType = "LOG"
			self.selectedDataType = ""
			self.selectedDepthType = ""
			self.OnEDIT_LOG(event)
		elif opId == 14 :
			# IMPORT STRAT 
			self.OnIMPORT_STRAT()
		elif opId == 15 :
			# IMPORT SPLICE TABLE
			self.OnIMPORT_TABLE("Splice")
		elif opId == 16 :
			# EXPORT
			self.OnExportSavedTable()
		elif opId == 17 :
			# IMPORT ELD TABLE
			self.OnIMPORT_TABLE("ELD")
		elif opId == 18 :
			# Edit Strat Type
			dlg = dialog.StratTypeDialog(self)
			dlg.Centre()
			ret = dlg.ShowModal()
			dlg.Destroy()
			if ret == wx.ID_OK :
				type = dlg.types.GetValue()
				self.tree.SetItemText(self.selectedIdx, type, 0)

				parentItem = self.tree.GetItemParent(self.selectedIdx)
				parentItem = self.tree.GetItemParent(parentItem)
				title = self.tree.GetItemText(parentItem, 0)
				filename = self.Set_NAMING(type, title, 'strat')
				oldfilename = self.tree.GetItemText(self.selectedIdx, 8)
				self.tree.SetItemText(self.selectedIdx,  filename, 8)

				fullname = self.parent.DBPath +'db/' + title + '/' + filename
				if sys.platform == 'win32' :
					workingdir = os.getcwd()
					os.chdir(self.parent.DBPath + 'db\\' + title)
					
					cmd = 'copy ' + oldfilename + ' ' + filename
					os.system(cmd)
					cmd = 'del \"' + oldfilename + '\"'
					os.system(cmd)
					os.chdir(workingdir)
				else :
					cmd = 'cp \"' + self.parent.DBPath +'db/' + title + '/' + oldfilename + '\" \"' + self.parent.DBPath +'db/' + title + '/' + filename + '\"' 
					#print "[DEBUG] " + cmd
					os.system(cmd)
					cmd = 'rm \"' + self.parent.DBPath +'db/' + title + '/' + oldfilename + '\"'
					# not do delete...
					os.system(cmd)

				tempstamp = str(datetime.today())
				last = tempstamp.find(":", 0)
				last = tempstamp.find(":", last+1)
				stamp = tempstamp[0:last]
				self.tree.SetItemText(self.selectedIdx, stamp, 6)
				self.OnUPDATE_DB_FILE(title, parentItem)
		elif opId == 19 :
			totalcount = self.tree.GetChildrenCount(self.selectedIdx, False)
			item = self.tree.GetItemParent(self.selectedIdx)
			if totalcount > 0 :
				child = self.tree.GetFirstChild(self.selectedIdx)
				child_item = child[0]
				self.tree.SetItemText(child_item, 'Enable', 2)
				for k in range(1, totalcount) :
					child_item = self.tree.GetNextSibling(child_item)
					self.tree.SetItemText(child_item, 'Enable', 2)
			else :
				self.tree.SetItemText(self.selectedIdx, 'Enable', 2)
				item = self.tree.GetItemParent(item)
			self.OnUPDATE_DB_FILE(self.tree.GetItemText(item, 0), item)
		elif opId == 20 :
			totalcount = self.tree.GetChildrenCount(self.selectedIdx, False)
			item = self.tree.GetItemParent(self.selectedIdx)
			if totalcount > 0 :
				child = self.tree.GetFirstChild(self.selectedIdx)
				child_item = child[0]
				self.tree.SetItemText(child_item, 'Disable', 2)
				for k in range(1, totalcount) :
					child_item = self.tree.GetNextSibling(child_item)
					self.tree.SetItemText(child_item, 'Disable', 2)
			else :
				self.tree.SetItemText(self.selectedIdx, 'Disable', 2)
				item = self.tree.GetItemParent(item)
			self.OnUPDATE_DB_FILE(self.tree.GetItemText(item, 0), item)
		elif opId == 21 :
			self.OnIMPORT_IMAGE()
		elif opId == 22 :
			print "Export XML Data!"
			# EXPORT XML TABLES
			type = self.tree.GetItemText(self.selectedIdx, 1)
			path = self.parent.DBPath + 'db/' + self.tree.GetItemText(self.selectedIdx, 10)
			filename = self.tree.GetItemText(self.selectedIdx, 8) 
			if type == "AFFINE" :
				self.SAVE_AFFINE_TO_XML(path, filename)
			elif type == "SPLICE" :
				self.SAVE_SPLICE_TO_XML(path, filename)
			elif type == "ELD" :
				self.SAVE_ELD_TO_XML(path, filename)
			elif type == "AGE/DEPTH" :
				title = self.tree.GetItemText(self.selectedIdx, 10) 
				max = len(title)
				last = title.find("-", 0)
				leg = title[0:last]
				site = title[last+1:max-1]
				self.SAVE_AGE_TO_XML(path, filename, leg, site)
			elif type == "AGE" :
				title = self.tree.GetItemText(self.selectedIdx, 10) 
				max = len(title)
				last = title.find("-", 0)
				leg = title[0:last]
				site = title[last+1:max-1]
				self.SAVE_SERIES_TO_XML(path, filename, leg, site)
			else :
				self.SAVE_CULL_TO_XML(path, filename)
		elif opId == 23 :
			print "Export Core Data!"
			self.EXPORT_CORE_DATA(self.selectedIdx, False)
		elif opId == 24 :
			self.IMPORT_AGE_MODEL()
		elif opId == 25 :
			print "Export Core Data (typed)!"
			self.EXPORT_CORE_DATA(self.selectedIdx, True)
		elif opId == 26 :
			self.tree.SetItemText(self.selectedIdx, "Discrete", 1) 
			item = self.tree.GetItemParent(self.selectedIdx)
			self.OnUPDATE_DB_FILE(self.tree.GetItemText(item, 0), item)
			self.parent.Window.UpdateDATATYPE(self.tree.GetItemText(self.selectedIdx, 0), False)
		elif opId == 27 :
			self.tree.SetItemText(self.selectedIdx, "Continuous",1) 
			item = self.tree.GetItemParent(self.selectedIdx)
			self.OnUPDATE_DB_FILE(self.tree.GetItemText(item, 0), item)
			self.parent.Window.UpdateDATATYPE(self.tree.GetItemText(self.selectedIdx, 0), True)
		elif opId == 28 :
			# VIEW SESSION LOG FILE
			filename = 'log/' + self.tree.GetItemText(self.selectedIdx, 1)
			if filename != "" :
				log = False
				if filename == self.parent.logName :
					self.parent.logFileptr.close()
					log = True 
				filename = self.parent.DBPath + filename
				self.fileText.Clear()
				self.fileText.LoadFile(filename)
				self.sideNote.SetSelection(2)
				if log == True :
					self.parent.OnReOpenLog()
		elif opId == 29 :
			deleted_flag = False
			selections = self.tree.GetSelections()
			ret = self.parent.OnShowMessage("About", "Do you want to delete?", 2)
			if ret == wx.ID_OK : 
				for select in selections :
					filename = 'log/' + self.tree.GetItemText(select, 1)
					if filename == self.parent.logName :
						self.parent.OnShowMessage("Error", "Can not delete current log", 1)
					else :
						deleted_flag = True 
						if sys.platform == 'win32' :
							filename = self.tree.GetItemText(select, 1)
							workingdir = os.getcwd()
							os.chdir(self.parent.DBPath + 'log/')
							os.system('del \"' + filename + '\"')
							os.chdir(workingdir)
						else :
							filename = self.parent.DBPath + 'log/' + self.tree.GetItemText(select, 1)
							os.system('rm \"'+ filename + '\"')
						self.tree.Delete(select)
			if deleted_flag == True :
				self.parent.OnShowMessage("Information", "Successfully deleted", 1)
		elif opId == 30 :
			# EMPTY
			ret = self.parent.OnShowMessage("About", "Do you want to make it Empty?", 2)
			if ret == wx.ID_OK : 
				if sys.platform == 'win32' :
					workingdir = os.getcwd()
					os.chdir(self.parent.DBPath + 'log/')
					totalcount = self.tree.GetChildrenCount(self.selectedIdx, False)
					if totalcount > 0 :
						child = self.tree.GetFirstChild(self.selectedIdx)
						child_item = child[0]
						filename = self.tree.GetItemText(child_item, 1)
						if filename != self.parent.logName :
							os.system('del \"' + filename + '\"')
						for k in range(1, totalcount) :
							child_item = self.tree.GetNextSibling(child_item)
							filename = self.tree.GetItemText(child_item, 1)
							if filename != self.parent.logName :
								os.system('del \"' + filename + '\"')
					os.chdir(workingdir)
				else :
					totalcount = self.tree.GetChildrenCount(self.selectedIdx, False)
					if totalcount > 0 :
						child = self.tree.GetFirstChild(self.selectedIdx)
						child_item = child[0]
						filename = 'log/' + self.tree.GetItemText(child_item, 1)
						if filename != self.parent.logName :
							os.system('rm \"'+ self.parent.DBPath + filename + '\"')
						for k in range(1, totalcount) :
							child_item = self.tree.GetNextSibling(child_item)
							filename = 'log/' + self.tree.GetItemText(child_item, 1)
							if filename != self.parent.logName :
								os.system('rm \"'+ self.parent.DBPath +filename + '\"')

				self.tree.Delete(self.selectedIdx)
				self.LoadSessionReports()
				self.parent.OnShowMessage("Information", "Successfully deleted", 1)
		elif opId == 31 :
			# EXPORT SESSION REPORT
			self.EXPORT_REPORT()
		elif opId == 32 :
			# 12/9/2013 brg: Import Universal cull table - menu item commented at present
			self.OnIMPORT_CULLTABLE(True)
		elif opId == 33 :
			self.IMPORT_TIME_SERIES()

		self.selectedIdx = None

	def ImportSectionSummary(self):
		secsumm = tabularImport.doImport(self, tabularImport.SectionSummaryFormat)
		if secsumm is not None:
			# udpate GUI
			site = self.GetSelectedSite()
			item = self.tree.GetSelection()
			self.tree.SetItemText(item, secsumm.name, 1)
			self.tree.SetItemText(item, secsumm.name, 10)
			
			# update site DB file
			self.OnUPDATE_DB_FILE(site, self.tree.GetItemParent(item))
			
			# write file
			sspath = self.parent.DBPath +'db/' + site + '/' + secsumm.name
			tabularImport.writeToFile(secsumm.dataframe, sspath)

	# get parent Site (child of Root node) for current selection in self.tree
	def GetSelectedSite(self):
		selsite = None
		selitem = self.tree.GetSelection()
		item = selitem
		while item is not None:
			parent = self.tree.GetItemParent(item)
			if parent is not None:
				if self.tree.GetItemText(parent, 0) == "Root":
					selsite = self.tree.GetItemText(item, 0)
					break
			item = parent
		return selsite

	# build appropriate right-click menu based on selection type - rather than pulling
	# text strings from the View to determine what's what, we should be asking the Model!
	def SelectTREE(self, event):
		pos = event.GetPosition()
		idx, flags, col = self.tree.HitTest(pos)
		if col >= 0 :
			self.selectedIdx = idx
			popupMenu = wx.Menu()

			str_name = self.tree.GetItemText(self.selectedIdx, 8)
			if str_name != "" :
				parentItem = self.tree.GetItemParent(self.selectedIdx)

				if self.tree.GetItemText(parentItem, 0) == "Saved Tables" or self.tree.GetItemText(self.selectedIdx, 0) == "-Cull Table" : 
					popupMenu.Append(2, "&View")
					wx.EVT_MENU(popupMenu, 2, self.OnPOPMENU)

					if self.tree.GetItemText(self.selectedIdx, 2) == "Disable" :
						popupMenu.Append(11, "&Enable")
						wx.EVT_MENU(popupMenu, 11, self.OnPOPMENU)
					else :
						popupMenu.Append(10, "&Disable")
						wx.EVT_MENU(popupMenu, 10, self.OnPOPMENU)

					popupMenu.Append(6, "&Delete")
					wx.EVT_MENU(popupMenu, 6, self.OnPOPMENU)
					popupMenu.Append(16, "&Export")
					wx.EVT_MENU(popupMenu, 16, self.OnPOPMENU)

					#popupMenu.Append(22, "&Export in XML")
					#wx.EVT_MENU(popupMenu, 22, self.OnPOPMENU)

				elif self.tree.GetItemText(parentItem, 0) == "Downhole Log Data" :
					popupMenu.Append(2, "&View")
					wx.EVT_MENU(popupMenu, 2, self.OnPOPMENU)

					popupMenu.Append(13, "&Edit")
					wx.EVT_MENU(popupMenu, 13, self.OnPOPMENU)

					if self.tree.GetItemText(self.selectedIdx, 2) == "Disable" :
						popupMenu.Append(11, "&Enable")
						wx.EVT_MENU(popupMenu, 11, self.OnPOPMENU)
					else :
						popupMenu.Append(10, "&Disable")
						wx.EVT_MENU(popupMenu, 10, self.OnPOPMENU)

					popupMenu.Append(6, "&Delete")
					wx.EVT_MENU(popupMenu, 6, self.OnPOPMENU)

				elif self.tree.GetItemText(parentItem, 0) == "Stratigraphy" :
					popupMenu.Append(2, "&View")
					wx.EVT_MENU(popupMenu, 2, self.OnPOPMENU)

					if self.tree.GetItemText(self.selectedIdx, 2) == "Disable" :
						popupMenu.Append(11, "&Enable")
						wx.EVT_MENU(popupMenu, 11, self.OnPOPMENU)
					else :
						popupMenu.Append(10, "&Disable")
						wx.EVT_MENU(popupMenu, 10, self.OnPOPMENU)

					popupMenu.Append(18, "&Edit")
					wx.EVT_MENU(popupMenu, 18, self.OnPOPMENU)

					popupMenu.Append(6, "&Delete")
					wx.EVT_MENU(popupMenu, 6, self.OnPOPMENU)
				elif self.tree.GetItemText(parentItem, 0) == "Age Models" :
					popupMenu.Append(2, "&View")
					wx.EVT_MENU(popupMenu, 2, self.OnPOPMENU)

					if self.tree.GetItemText(self.selectedIdx, 2) == "Disable" :
						popupMenu.Append(11, "&Enable")
						wx.EVT_MENU(popupMenu, 11, self.OnPOPMENU)
					else :
						popupMenu.Append(10, "&Disable")
						wx.EVT_MENU(popupMenu, 10, self.OnPOPMENU)

					popupMenu.Append(6, "&Delete")
					wx.EVT_MENU(popupMenu, 6, self.OnPOPMENU)

					popupMenu.Append(16, "&Export")
					wx.EVT_MENU(popupMenu, 16, self.OnPOPMENU)

					popupMenu.Append(22, "&Export in XML")
					wx.EVT_MENU(popupMenu, 22, self.OnPOPMENU)

				elif self.tree.GetItemText(parentItem, 0) == "Image Data" :
					popupMenu.Append(2, "&View")
					wx.EVT_MENU(popupMenu, 2, self.OnPOPMENU)

					popupMenu.Append(6, "&Delete")
					wx.EVT_MENU(popupMenu, 6, self.OnPOPMENU)

					popupMenu.Append(16, "&Export")
					wx.EVT_MENU(popupMenu, 16, self.OnPOPMENU)
				else :
					popupMenu.Append(1, "&Load")
					wx.EVT_MENU(popupMenu, 1, self.OnPOPMENU)

					popupMenu.Append(2, "&View")
					wx.EVT_MENU(popupMenu, 2, self.OnPOPMENU)

					popupMenu.Append(3, "&Edit")
					wx.EVT_MENU(popupMenu, 3, self.OnPOPMENU)

					if self.tree.GetItemText(self.selectedIdx, 2) == "Disable" :
						popupMenu.Append(19, "&Enable")
						wx.EVT_MENU(popupMenu, 19, self.OnPOPMENU)
					else :
						popupMenu.Append(20, "&Disable")
						wx.EVT_MENU(popupMenu, 20, self.OnPOPMENU)

					popupMenu.Append(6, "&Delete")
					wx.EVT_MENU(popupMenu, 6, self.OnPOPMENU)

					popupMenu.Append(7, "&Update")
					wx.EVT_MENU(popupMenu, 7, self.OnPOPMENU)

					popupMenu.Append(23, "&Export")
					wx.EVT_MENU(popupMenu, 23, self.OnPOPMENU)

					#popupMenu.Append(23, "&Export in XML")
					#wx.EVT_MENU(popupMenu, 23, self.OnPOPMENU)

			else :
				str_name = self.tree.GetItemText(self.selectedIdx, 0)
				if str_name == "Session Reports" :
					popupMenu.Append(30, "&Empty")
					wx.EVT_MENU(popupMenu, 30, self.OnPOPMENU)
				elif str_name == "Report" :
					popupMenu.Append(28, "&View")
					wx.EVT_MENU(popupMenu, 28, self.OnPOPMENU)

					popupMenu.Append(29, "&Delete")
					wx.EVT_MENU(popupMenu, 29, self.OnPOPMENU)

					popupMenu.Append(31, "&Export")
					wx.EVT_MENU(popupMenu, 31, self.OnPOPMENU)
				elif str_name == "Saved Tables" :
					popupMenu.Append(4, "&Import affine table")
					wx.EVT_MENU(popupMenu, 4, self.OnPOPMENU)

					popupMenu.Append(15, "&Import splice table")
					wx.EVT_MENU(popupMenu, 15, self.OnPOPMENU)

					popupMenu.Append(17, "&Import ELD table")
					wx.EVT_MENU(popupMenu, 17, self.OnPOPMENU)

					#popupMenu.Append(32, "&Import universal cull table")
					#wx.EVT_MENU(popupMenu, 32, self.OnPOPMENU)

				elif str_name == "Downhole Log Data" :
					popupMenu.Append(12, "&Import log")
					wx.EVT_MENU(popupMenu, 12, self.OnPOPMENU)
				elif str_name == "Root" :
					popupMenu.Append(5, "&Add new data")
					wx.EVT_MENU(popupMenu, 5, self.OnPOPMENU)

					popupMenu.Append(6, "&Delete")
					wx.EVT_MENU(popupMenu, 6, self.OnPOPMENU)

					#popupMenu.Append(7, "&Update")
					#wx.EVT_MENU(popupMenu, 7, self.OnPOPMENU)
				elif str_name == "Stratigraphy" :
					popupMenu.Append(14, "&Import stratigraphy data")
					wx.EVT_MENU(popupMenu, 14, self.OnPOPMENU)
				elif str_name == "Age Models" :
					popupMenu.Append(24, "&Import age/depth table")
					wx.EVT_MENU(popupMenu, 24, self.OnPOPMENU)

					popupMenu.Append(33, "&Import age model")
					wx.EVT_MENU(popupMenu, 33, self.OnPOPMENU)
				elif str_name == "Image Data" :
					popupMenu.Append(21, "&Import image data")
					wx.EVT_MENU(popupMenu, 21, self.OnPOPMENU)
				elif str_name == "Section Summary":
					secsumm_name = self.tree.GetItemText(self.selectedIdx, 1)
					if secsumm_name == "":
						popupMenu.Append(1, "&Import Section Summary...")
						wx.EVT_MENU(popupMenu, 1, self.OnSecSummMenu)
					else:
						popupMenu.Append(2, "&View")
						path = self.parent.DBPath + 'db/' + self.GetSelectedSite() + '/' + secsumm_name
						wx.EVT_MENU(popupMenu, 2, self.OnSecSummMenu)
						popupMenu.Append(3, "&Delete")
						wx.EVT_MENU(popupMenu, 3, self.OnSecSummMenu)
				else :
					popupMenu.Append(5, "&Add new data")
					wx.EVT_MENU(popupMenu, 5, self.OnPOPMENU)

					popupMenu.Append(1, "&Load")
					wx.EVT_MENU(popupMenu, 1, self.OnPOPMENU)

					parentItem = self.tree.GetItemParent(self.selectedIdx)
					if self.tree.GetItemText(parentItem, 0) != "Root" :
						popupMenu.Append(3, "&Edit")
						wx.EVT_MENU(popupMenu, 3, self.OnPOPMENU)

						if self.tree.GetItemText(self.selectedIdx, 1) == "Continuous" :
							popupMenu.Append(26, "&Discrete")
							wx.EVT_MENU(popupMenu, 26, self.OnPOPMENU)
						else :
							popupMenu.Append(27, "&Continuous")
							wx.EVT_MENU(popupMenu, 27, self.OnPOPMENU)

						popupMenu.Append(19, "&Enable")
						wx.EVT_MENU(popupMenu, 19, self.OnPOPMENU)
						popupMenu.Append(20, "&Disable")
						wx.EVT_MENU(popupMenu, 20, self.OnPOPMENU)

						popupMenu.Append(6, "&Delete")
						wx.EVT_MENU(popupMenu, 6, self.OnPOPMENU)

						popupMenu.Append(9, "&Import cull table")
						wx.EVT_MENU(popupMenu, 9, self.OnPOPMENU)

						popupMenu.Append(7, "&Update")
						wx.EVT_MENU(popupMenu, 7, self.OnPOPMENU)

						popupMenu.Append(25, "&Export")
						wx.EVT_MENU(popupMenu, 25, self.OnPOPMENU)
					else :
						popupMenu.Append(6, "&Delete")
						wx.EVT_MENU(popupMenu, 6, self.OnPOPMENU)

						popupMenu.Append(7, "&Update")
						wx.EVT_MENU(popupMenu, 7, self.OnPOPMENU)

			self.tree.PopupMenu(popupMenu, pos)
		return


	def EXPORT_CORE_DATA(self, selectedIdx, isType) :
		dlg = dialog.ExportCoreDialog(self)
		dlg.Centre()
		ret = dlg.ShowModal()
		if ret == wx.ID_OK :
			#opendlg = wx.DirDialog(self, "Select Directory For Export", self.parent.Directory)
			opendlg = wx.FileDialog(self, "Select Directory For Export", self.parent.Directory, style=wx.SAVE)
			ret = opendlg.ShowModal()
			#output_path = opendlg.GetPath()
			output_path = opendlg.GetDirectory()
			output_prefix = opendlg.GetFilename()
			self.parent.Directory = output_path
			opendlg.Destroy()
			if ret != wx.ID_OK :
				return

			if isType == False :
				parentItem = self.tree.GetItemParent(selectedIdx)
			else : 
				parentItem = selectedIdx 

			datatype = self.tree.GetItemText(parentItem, 0) 
			#print "[DEBUG] datatype = " + datatype

			# LEG-SITE LEVEL
			parentItem = self.tree.GetItemParent(parentItem)
			title = self.tree.GetItemText(parentItem, 0) 

			child = self.FindItem(parentItem, 'Saved Tables')
			cull_item = None
			affine_item = None
			splice_item = None
			eld_item = None
			if child[0] == True :
				selectItem = child[1]
				totalcount = self.tree.GetChildrenCount(selectItem, False)
				if totalcount > 0 :
					child = self.tree.GetFirstChild(selectItem)
					child_item = child[0]
					type = self.tree.GetItemText(child_item, 1)
					flag = self.tree.GetItemText(child_item, 2)
					if type == "AFFINE" and flag == "Enable" :
						affine_item = child_item 
					elif type == "SPLICE" and flag == "Enable" :
						splice_item = child_item 
					elif type == "ELD" and flag == "Enable" :
						eld_item = child_item 
					for k in range(1, totalcount) :
						child_item = self.tree.GetNextSibling(child_item)
						type = self.tree.GetItemText(child_item, 1)
						flag = self.tree.GetItemText(child_item, 2)
						if type == "AFFINE" and flag == "Enable" :
							affine_item = child_item 
						elif type == "SPLICE" and flag == "Enable" :
							splice_item = child_item 
						elif type == "ELD" and flag == "Enable" :
							eld_item = child_item 

			child = self.FindItem(parentItem, 'Age Models')
			age_item = None
			if child[0] == True :
				selectItem = child[1]
				totalcount = self.tree.GetChildrenCount(selectItem, False)
				if totalcount > 0 :
					child = self.tree.GetFirstChild(selectItem)
					child_item = child[0]
					type = self.tree.GetItemText(child_item, 1)
					flag = self.tree.GetItemText(child_item, 2)
					if type == "AGE" and flag == "Enable" :
						age_item = child_item 
					for k in range(1, totalcount) :
						child_item = self.tree.GetNextSibling(child_item)
						type = self.tree.GetItemText(child_item, 1)
						flag = self.tree.GetItemText(child_item, 2)
						if type == "AGE" and flag == "Enable" :
							age_item = child_item 


			child = self.FindItem(parentItem, 'Downhole Log Data')
			log_item = None
			if child[0] == True :
				selectItem = child[1]
				totalcount = self.tree.GetChildrenCount(selectItem, False)
				if totalcount > 0 :
					child = self.tree.GetFirstChild(selectItem)
					child_item = child[0]
					flag = self.tree.GetItemText(child_item, 2)
					if flag == "Enable" :
						log_item = child_item
					else :
						for k in range(1, totalcount) :
							child_item = self.tree.GetNextSibling(child_item)
							flag = self.tree.GetItemText(child_item, 2)
							if flag == "Enable" :
								log_item = child_item
								break

			type, annot = self.parent.TypeStrToInt(datatype)
			datatype = self.parent.TypeStrToFileSuffix(datatype, True)

			if isType == False :
				parentItem = self.tree.GetItemParent(selectedIdx)
				totalcount = self.tree.GetChildrenCount(parentItem, False)
				if totalcount > 0 :
					child = self.tree.GetFirstChild(parentItem)
					child_item = child[0]
					if self.tree.GetItemText(child_item, 0) == "-Cull Table" and self.tree.GetItemText(child_item, 2) == "Enable" :
						cull_item = child_item
					else :
						for k in range(1, totalcount) :
							child_item = self.tree.GetNextSibling(child_item)
							if self.tree.GetItemText(child_item, 0) == "-Cull Table" and self.tree.GetItemText(child_item, 2) == "Enable" :
								cull_item = child_item
								break
			else :
				parentItem = selectedIdx

			# LOADING DATA
			self.parent.OnNewData(None)
			path = self.parent.DBPath + 'db/' + title + "/"

			holes = []
			if dlg.splice.GetValue() == True or isType == True :
				totalcount = self.tree.GetChildrenCount(parentItem, False)
				if totalcount > 0 :
					child = self.tree.GetFirstChild(parentItem)
					child_item = child[0]
					if self.tree.GetItemText(child_item, 0)  != "-Cull Table" :
						filename = self.tree.GetItemText(child_item, 8) 
						ret = py_correlator.openHoleFile(path + filename, -1, type, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, annot)
						holes.append(self.tree.GetItemText(child_item, 0))
					elif self.tree.GetItemText(child_item, 2) == "Enable" and cull_item == None :
						cull_item = child_item
					for k in range(1, totalcount) :
						child_item = self.tree.GetNextSibling(child_item)
						if self.tree.GetItemText(child_item, 0)  != "-Cull Table" :
							filename = self.tree.GetItemText(child_item, 8) 
							ret = py_correlator.openHoleFile(path + filename, -1, type, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, annot)
							holes.append(self.tree.GetItemText(child_item, 0))
						elif self.tree.GetItemText(child_item, 2) == "Enable" and cull_item == None :
							cull_item = child_item

			else :
				filename = self.tree.GetItemText(selectedIdx, 8) 
				ret = py_correlator.openHoleFile(path + filename, -1, type, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, annot)
				holes.append(self.tree.GetItemText(selectedIdx, 0))

			applied = ""
			# APPLY TABLES 
			if dlg.cull.GetValue() == True and cull_item != None:
				py_correlator.openCullTable(path + self.tree.GetItemText(cull_item, 8), type, annot)
				applied = "cull"

			if dlg.affine.GetValue() == True and affine_item != None:
				py_correlator.openAttributeFile(path + self.tree.GetItemText(affine_item, 8), 0)
				applied = "affine"

			if dlg.splice.GetValue() == True and splice_item != None :
				ret_splice = py_correlator.openSpliceFile(path +self.tree.GetItemText(splice_item, 8))
				if ret_splice == "error" : 
					self.parent.OnShowMessage("Error", "Could not Make Splice Records", 1)
				applied = "splice"
			elif dlg.splice.GetValue() == True and splice_item == None :
				self.parent.OnShowMessage("Error", "Can not export -need splice table", 1)
				self.parent.OnNewData(None)
				dlg.Destroy()
				return

			# HYEJUNG
			if dlg.eld.GetValue() == True and eld_item != None :
				if log_item != None :
					py_correlator.openLogFile(path+ self.tree.GetItemText(log_item, 8), int(self.tree.GetItemText(log_item, 11)))
					py_correlator.openAttributeFile(path + self.tree.GetItemText(eld_item, 8), 1)
					applied = "eld"
				else :
					self.parent.OnShowMessage("Error", "Need Log to Export ELD", 1)
					self.parent.OnNewData(None)
					dlg.Destroy()
					return

			useCsv = dlg.csvFormat.GetValue()
			if useCsv:
				py_correlator.setDelimiter(1) # write comma-delimited file for export
			
			count = 0
			if dlg.age.GetValue() == True and age_item != None :
				applied += "-age"
				agefilename = path+ self.tree.GetItemText(age_item, 8)
				if dlg.eld.GetValue() == True :
					if dlg.splice.GetValue() == True :
						count = py_correlator.saveAgeCoreData(agefilename, path + ".export.tmp", 2)
					else :
						count = py_correlator.saveAgeCoreData(agefilename, path + ".export.tmp", 0)
				else :
					if dlg.splice.GetValue() == True :
						count = py_correlator.saveAgeCoreData(agefilename, path + ".export.tmp", 1)
					else :
						count = py_correlator.saveAgeCoreData(agefilename, path + ".export.tmp", 0)
			elif dlg.eld.GetValue() == True :
				if dlg.splice.GetValue() == True :
					count = py_correlator.saveCoreData(path + ".export.tmp", 2)
				else :
					count = py_correlator.saveCoreData(path + ".export.tmp", 0)
			elif dlg.splice.GetValue() == True :
				count = py_correlator.saveCoreData(path + ".export.tmp", 1)
			else :
				count = py_correlator.saveCoreData(path + ".export.tmp", 0)
				
			if useCsv:
				py_correlator.setDelimiter(0) # reset delimiter to space + tab so internal files are written normally
			outExtension = ".csv" if useCsv else ".dat"

			self.parent.OnNewData(None)

			if dlg.splice.GetValue() == True and count == 1 :
				if dlg.xmlFormat.GetValue():
					outfile = output_prefix + "-" + title + "-" + applied + "." + datatype + outExtension
					self.SAVE_CORE_TO_XML(path, ".export.tmp", output_path, outfile, dlg.age.GetValue(), dlg.splice.GetValue())
				else :
					outfile = output_prefix + "-" + title + "-" + applied + "." + datatype + outExtension
					if sys.platform == 'win32' :
						workingdir = os.getcwd()
						os.chdir(path)
						cmd = 'copy ' +  ".export.tmp" + ' \"' + output_path + '/' + outfile + '\"'
						os.system(cmd)
						os.chdir(workingdir)
					else :
						cmd = 'cp \"' +  path + ".export.tmp" + '\" \"' + output_path + '/' + outfile + '\"'
						os.system(cmd)
			else :
				for i in range(count) :
					outfile = output_prefix + "-" + title + "-" + applied + holes[i] + "." + datatype + outExtension
					if dlg.xmlFormat.GetValue():
						self.SAVE_CORE_TO_XML(path, ".export.tmp"+ str(i), output_path, outfile, dlg.age.GetValue(), dlg.splice.GetValue())
					else :
						if sys.platform == 'win32' :
							workingdir = os.getcwd()
							os.chdir(path)
							cmd = 'copy ' +  ".export.tmp" + str(i) + ' \"' + output_path + '/' + outfile + '\"'
							os.system(cmd)
							os.chdir(workingdir)
						else :
							cmd = 'cp \"' +  path + ".export.tmp" + str(i) + '\" \"' + output_path + '/' + outfile + '\"'
							os.system(cmd)

			if count > 0 :
				self.parent.OnShowMessage("Information", "Successfully exported", 1)
			else :
				self.parent.OnShowMessage("Error", "Can not export", 1)

		dlg.Destroy()

	def SAVE_AFFINE_TO_XML(self, affineFile, outFile):
		fin = open(affineFile, 'r+')
		fout = open(outFile + '.xml', 'w+')
		fout.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
		fout.write("<Correlator version=\"1.0\">\n")

		idx = 0
		prevHole = ""
		for line in fin :
			#token = line.split(' \t')
			token = line.split()
			if len(token) == 1 : 
				continue

			first = token[0]
			if first[0] == '#' : continue

			if idx == 0 :
				fout.write("\t<Data type=\"affine table\" leg=\"" + token[0] + "\" site=\""+ token[1] + "\">\n")
				idx = 1

			if prevHole != token[2] :
				if prevHole != "" :
					fout.write("\t\t</Hole>\n")
				fout.write("\t\t<Hole value=\"" + token[2] + "\">\n")
			applied = token[6]
			fout.write("\t\t\t<Core id=\"" + token[3] + "\" type=\"" + token[4] + "\" applied=\"" + applied[0]+ "\" offset =\"" + token[5]+ "\" />\n")

			prevHole = token[2]
				
		if prevHole != "" :
			fout.write("\t\t</Hole>\n")
			fout.write("\t</Data>\n")
		fout.write("</Correlator>\n")
		fout.close()
		fin.close()

	def SAVE_SPLICE_TO_XML(self, spliceFile, outFile):
		affinetable = "None"
		fin = open(spliceFile, 'r+')
		fout = open(outFile + '.xml', 'w+')
		fout.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
		fout.write("<Correlator version=\"1.0\">\n")

		idx = 0
		for line in fin :
			#token = line.split(' \t')
			token = line.split()
			token_size =  len(token)
			if token_size == 1 : 
				continue

			first = token[0]
			if first[0] == '#' : 
				if token[1] == 'AffineTable' : 
					affinetable = token[2]
				continue

			if idx == 0:
				# find leg
				title = self.tree.GetItemText(self.selectedIdx, 10) 
				last = title.find("-", 0)
				leg = title[0:last]
				fout.write("\t<Data type =\"splice table\" leg =\"" + leg + "\" site=\""+ token[0] + "\" affinefilename=\"" + affinetable +"\">\n")
			fout.write("\t\t<Tie id=\"" + str(idx) + "\">\n")

			if token_size < 19 : 
				temp_token = token[8]
				last = temp_token.find("\r", 0)
				if last < 0 :
					last = temp_token.find("\n", 0)
				last_token = temp_token[0:last]

				fout.write("\t\t\t<Core id=\"" + token[2] + "\" hole=\"" + token[1] + "\" type=\"" + token[3] + "\" section=\"" + token[4] + "\" top=\"" + token[5] + "\" bottom=\"" + token[6] + "\" mbsf=\"" + token[7] + "\" mcd=\"" + last_token + "\"/>\n")

				cmd = "tied"
				if token_size < 10 :
                                            cmd = "append"
				elif token[9].find("APPEND", 0) >= 0 or token[9].find("append", 0) >= 0 :
					cmd = "append"

				if token_size < 11 : 
					fout.write("\t\t\t<Core tietype=\"" + cmd + "\"/>\n")
				else :
					fout.write("\t\t\t<Core tietype=\"" + cmd + "\" id=\"" + token[12] + "\" hole=\"" + token[11] + "\" type=\"" + token[13] + "\" section=\"" + token[14] + "\" top=\"" + token[15] + "\" bottom=\""+ token[16] + "\" mbsf=\"" + token[17] + "\" mcd=\"" + last_token + "\"/>\n")


			else :
				fout.write("\t\t\t<Core id=\"" + token[2] + "\" hole=\"" + token[1] + "\" type=\"" + token[3] + "\" section=\"" + token[4] + "\" top=\"" + token[5] + "\" bottom=\"" + token[6] + "\" mbsf=\"" + token[7] + "\" mcd=\"" + token[8] + "\"/>\n")

				temp_token = token[18]
				last = temp_token.find("\r", 0)
				if last < 0 :
					last = temp_token.find("\n", 0)
				last_token = temp_token
				if last != -1 :
					last_token = temp_token[0:last]
				#print temp_token, last_token, last

				cmd = "tied"
				if token[9] == "APPEND" or token[9] == "append" :
					cmd = "append"

				if token_size < 11 : 
					fout.write("\t\t\t<Core tietype=\"" + cmd + "\"/>\n")
				else :
					fout.write("\t\t\t<Core tietype=\"" + cmd + "\" id=\"" + token[12] + "\" hole=\"" + token[11] + "\" type=\"" + token[13] + "\" section=\"" + token[14] + "\" top=\"" + token[15] + "\" bottom=\""+ token[16] + "\" mbsf=\"" + token[17] + "\" mcd=\"" + last_token + "\"/>\n")

			fout.write("\t\t</Tie>\n")

			idx += 1 
				
		if idx != 0 :
			fout.write("\t</Data>\n")
		fout.write("</Correlator>\n")
		fout.close()
		fin.close()
		#self.parent.OnShowMessage("Information", "Successfully exported", 1)


	def SAVE_ELD_TO_XML(self, source_path, filename):
		#opendlg = wx.DirDialog(self, "Select Directory For Export", self.parent.Directory)
		opendlg = wx.FileDialog(self, "Select Directory For Export", self.parent.Directory, style=wx.SAVE)
		ret = opendlg.ShowModal()
		#path = opendlg.GetPath()
		path = opendlg.GetDirectory()
		outfile = opendlg.GetFilename()
		self.parent.Directory = path
		opendlg.Destroy()
		if ret == wx.ID_OK :
			fin = open(source_path + filename, 'r+')
			fout = open(path + '/' + outfile + '.xml', 'w+')
			fout.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
			fout.write("<Correlator version=\"1.0\">\n")

			idx = 0
			leg = ""
			site = ""
			offset = ""
			rate = ""
			applied = ""
			prevHole = ""
			close_flag = True 

			for line in fin :
				#token = line.split(' \t')
				token = line.split()
				if len(token) == 1 : 
					continue

				if token[0][0] == "#" : continue

				if token[0][0] == "E" :
					count = 0
					for sub_token in token :
						if sub_token == "Leg" :
							leg = token[count + 1]
							break
						count += 1 
					count = len(token) -1
					#leg = token[2]
					temp_token = token[count]
					site = temp_token
					last = temp_token.find("\n", 0)
					if last > 0 :
						site = temp_token[0:last]
				elif token[0][0] == "O" :
					offset = token[3]
					applied = token[1]
					temp_token = token[5]
					last = temp_token.find("\n", 0)
					rate = temp_token[0:last]
				elif token[0][0] == "A" :
					if token[1][0] == "Y" :
						temp_token = token[2]
						last = temp_token.find("\n", 0)
						last_token = temp_token[0:last]
						fout.write("\t<Data type =\"eld table\" leg =\"" + leg + "\" site=\""+ site + "\" mudlineoffset=\"" + offset + "\" stretchrate=\"" + rate + "\" applied=\"" + applied + "\" affinetable=\"" + last_token + "\">\n")
					else :
						fout.write("\t<Data type =\"eld table\" leg =\"" + leg + "\" site=\""+ site + "\" mudlineoffset=\"" + offset + "\" stretchrate=\"" + rate + "\" applied=\"" + applied + "\">\n")
					idx = 1
				elif token[0][0] == "H" :
					if close_flag == False :
						fout.write("\t\t\t</Core>\n")
					if prevHole != token[1] :
						if prevHole != "" :
							fout.write("\t\t</Hole>\n")
						fout.write("\t\t<Hole value=\"" + token[1] + "\">\n")
					if token[8][0] == "0" :
						fout.write("\t\t\t<Core id=\"" + token[3] + "\" applied=\"" + token[6] + "\" offset =\"" + token[5] + "\" />\n")
						close_flag = True 
					else :
						fout.write("\t\t\t<Core id=\"" + token[3] + "\" applied=\"" + token[6] + "\" offset =\"" + token[5] + "\">\n")
						close_flag = False 
						
					prevHole = token[1]
				else :
					temp_token = token[12]
					last = temp_token.find("\n", 0)
					last_token = temp_token[0:last]
					fout.write("\t\t\t\t<LogTie id=\"0\" type=\"" + token[3] + "\" section=\"" + token[4] + "\" bottom=\"" + token[5] + "\" top=\"" + token[6] + "\" mbsf=\"" + token[7] + "\" mcd=\"" + token[8] +"\" a=\"" + token[9] + "\" b=\"" + token[10] + "\" share=\"" + token[11] + "\" eld=\"" + last_token + "\" />\n")

			if close_flag == False :
				fout.write("\t\t\t</Core>\n")
			if prevHole != "" :
				fout.write("\t\t</Hole>\n")
			if idx != 0 :
				fout.write("\t</Data>\n")
			fout.write("</Correlator>\n")
			fout.close()
			fin.close()
			self.parent.OnShowMessage("Information", "Successfully exported", 1)


	def SAVE_CULL_TO_XML(self, source_path, filename):
		#opendlg = wx.DirDialog(self, "Select Directory For Export", self.parent.Directory)
		opendlg = wx.FileDialog(self, "Select Directory For Export", self.parent.Directory, style=wx.SAVE)
		ret = opendlg.ShowModal()
		#path = opendlg.GetPath()
		path = opendlg.GetDirectory()
		outfile = opendlg.GetFilename()
		self.parent.Directory = path
		opendlg.Destroy()
		if ret == wx.ID_OK :
			fin = open(source_path + filename, 'r+')
			fout = open(path + '/' + outfile + '.xml', 'w+')
			fout.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
			fout.write("<Correlator version=\"1.0\">\n")

			idx = 0
			prevHole = ""
			prevCore = ""
			dataType = ""
			top = ""
			range = ""
			core = ""
			for line in fin :
				if line[0] == "#" :
					token = line.split()
					if token[0] == 'null' :
						continue
					if token[1] == "Data" :
						last = line.find("Type", 0)
						temp_token = line[last+5:-1]
						last = len(temp_token) -1
						dataType = temp_token
						if temp_token[last] == '\n' :
							dataType = temp_token[0:last]
					elif token[1] == "Type" :
						last = line.find("Type", 0)
						temp_token = line[last+5:-1]
						last = len(temp_token) -1
						dataType = temp_token
						if temp_token[last] == '\n' :
							dataType = temp_token[0:last]
					elif token[1] == "Top" :
						top = token[2]
						last = len(top) -1
						if top[last] == '\n' :
							top = top[0:last]
					elif token[1] == "Range" :
						temp_token = line[8:-1]
						last = len(temp_token) -1
						range = temp_token
						if temp_token[last] == '\n' :
							range = temp_token[0:last]
					elif token[1] == "Core" :
						core = token[2]
						last = len(core) -1
						if core[last] == '\n' :
							core = core[0:last]
					continue

				token = line.split(' \t')
				if len(token) == 1 : 
					continue

				if idx == 0 :
					str_temp = "\t<Data type =\"cull table\" leg =\"" + token[0] + "\" site=\""+ token[1] + "\" "
					if top != "" :
						str_temp += "cull_top=\""+ top + "\" "
					if core != "" :
						str_temp += "cull_core=\""+ core + "\" "

					if range != "" :
						range_token = range.split()
						range_str = ""
						if range_token[0] == '>' : 
							range_str ="greater "
						else :
							range_str ="less "
						range_str += range_token[1] 
						if len(range_token) > 2 :
							if range_token[2] == '>' : 
								range_str +=" greater "
							else :
								range_str +=" less "
							range_str += range_token[3] 

						str_temp += "cull_range=\""+ range_str + "\" "

					if dataType != "" :
						str_temp += "datatype=\"" + dataType + "\">\n"
						#fout.write("\t<Data type =\"cull table\" leg =\"" + token[0] + "\" site=\""+ token[1] + "\" datatype=\"" + dataType + "\">\n")
					else :
						str_temp += "datatype=\"\">\n"
						#fout.write("\t<Data type =\"cull table\" leg =\"" + token[0] + "\" site=\""+ token[1] + "\">\n")
					fout.write(str_temp)

					idx = 1

				if prevHole != token[2] :
					if prevCore != token[3] and prevCore != "" :
						fout.write("\t\t\t</Core>\n")
					if prevHole != "" :
						fout.write("\t\t</Hole>\n")
						prevCore = ""
					fout.write("\t\t<Hole value=\"" + token[2] + "\">\n")

				if prevCore != token[3] :
					if prevCore != "" :
						fout.write("\t\t\t</Core>\n")
					if token[4] == "badcore" :
						fout.write("\t\t\t<Core id=\"" + token[3] + "\" flag=\"badcore\">\n")
					else :
						fout.write("\t\t\t<Core id=\"" + token[3] + "\">\n")

				if token[4] != "badcore" :
					temp_token = token[5]
					if temp_token[0] == " " :
						temp_token = token[5][1]

					fout.write("\t\t\t\t<Value type=\"" + token[4] + "\" section=\"" + temp_token + "\" top =\"" + token[6]+ "\" bottom =\"" + token[7] + "\" />\n")

				prevHole = token[2]
				prevCore = token[3] 
					
			if prevCore != "" :
				fout.write("\t\t\t</Core>\n")

			if prevHole != "" :
				fout.write("\t\t</Hole>\n")
				fout.write("\t</Data>\n")
			fout.write("</Correlator>\n")
			fout.close()
			fin.close()
			self.parent.OnShowMessage("Information", "Successfully exported", 1)


	def SAVE_SERIES_TO_XML(self, source_path, filename, leg, site):
		#opendlg = wx.DirDialog(self, "Select Directory For Export", self.parent.Directory)
		opendlg = wx.FileDialog(self, "Select Directory For Export", self.parent.Directory, style=wx.SAVE)
		ret = opendlg.ShowModal()
		#path = opendlg.GetPath()
		path = opendlg.GetDirectory()
		outfile = opendlg.GetFilename()
		self.parent.Directory = path
		opendlg.Destroy()
		if ret == wx.ID_OK :
			fin = open(source_path + filename, 'r+')
			fout = open(path + '/' + outfile + '.xml', 'w+')
			fout.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
			fout.write("<Correlator version=\"1.0\">\n")

			idx = 0
			for line in fin :
				if line[0] == "#" :
					continue

				token = line.split(' \t')
				if len(token) == 1 : 
					continue

				if idx == 0 :
					fout.write("\t<Data type =\"age model\" leg =\"" + str(leg) + "\" site =\"" + str(site)+ "\">\n")

				temp_token = token[9]
				last = temp_token.find("\n", 0)
				last_token = temp_token[0:last]

				fout.write("\t\t<Stratigraphy id=\"" + str(idx) + "\" mbsf=\"" + token[2] + "\" mcd =\"" + token[3]+ "\" eld =\"" + token[4] + "\" age=\""+ token[5] +"\" sedrate=\"" + token[6] + "\" agedatum=\"" + token[7] + "\" comment=\"" + token[8] + "\" type=\"" + last_token + "\"/>\n")

				idx += 1

			if idx != 0 :
				fout.write("\t</Data>\n")
			fout.write("</Correlator>\n")
			fout.close()
			fin.close()
			self.parent.OnShowMessage("Information", "Successfully exported", 1)


	def SAVE_AGE_TO_XML(self, source_path, filename, leg, site):
		#opendlg = wx.DirDialog(self, "Select Directory For Export", self.parent.Directory)
		opendlg = wx.FileDialog(self, "Select Directory For Export", self.parent.Directory, style=wx.SAVE)
		ret = opendlg.ShowModal()
		#path = opendlg.GetPath()
		path = opendlg.GetDirectory()
		outfile = opendlg.GetFilename()
		self.parent.Directory = path
		opendlg.Destroy()
		if ret == wx.ID_OK :
			fin = open(source_path + filename, 'r+')
			fout = open(path + '/' + outfile + '.xml', 'w+')
			fout.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
			fout.write("<Correlator version=\"1.0\">\n")

			idx = 0
			for line in fin :
				if line[0] == "#" :
					continue

				#token = line.split(' \t')
				token = line.split()
				if len(token) == 1 : 
					continue

				if idx == 0 :
					#fout.write("\t<Data type =\"agedepth\" leg =\"" + leg + "\" site=\""+ site + "\">\n")
					fout.write("\t<Data type =\"age depth\">\n")

				temp_token = token[2]
				last = temp_token.find(" ", 0)
				label = temp_token[0:last]
				start = last +1
				last = temp_token.find("\n", start)
				last_token = temp_token[start:last]

				#fout.write("\t\t<Stratigraphy id=\"" + str(idx) + "\" mbsf=\"" + token[0] + "\" mcd =\"" + token[1]+ "\" eld =\"" + token[2] + "\" age=\""+ token[3] +"\" sedrate=\"" + token[4] +"\" name=\"" + token[5]+ "\" label=\"" + label+ "\" type=\"" + last_token + "\" />\n")
				fout.write("\t\t<Stratigraphy id=\"" + str(idx) + "\" depth=\"" + token[0] + "\" age=\""+ token[1] +"\" controlpoint=\"" + label+ "\" type=\"" + last_token + "\" />\n")

				idx += 1

			if idx != 0 :
				fout.write("\t</Data>\n")
			fout.write("</Correlator>\n")
			fout.close()
			fin.close()
			self.parent.OnShowMessage("Information", "Successfully exported", 1)


	def SAVE_CORE_TO_XML(self, source_path, src_file, dest_path, dest_file, age_flag, splice_flag):
		fin = open(source_path + src_file, 'r+')
		fout = open(dest_path + '/' + dest_file + '.xml', 'w+')
		fout.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
		fout.write("<Correlator version=\"1.0\">\n")

		idx = 0
		prevHole = ""
		prevCore = ""
		dataType = ""
		for line in fin :
			if line[0] == "#" :
				token = line.split()
				if token[0] == 'null' :
					continue
				if token[1] == "Data" :
					last = line.find("Type", 0)
					temp_token = line[last+5:-1]
					if temp_token != "" :
						last = len(temp_token) -1
						dataType = temp_token
						if temp_token[last] == '\n' :
							dataType = temp_token[0:last]
				continue

			token = line.split(' \t')
			max_len = len(token)
			if max_len == 1 : 
				continue

			if idx == 0 :
				fout.write("\t<Data type =\"core data\" leg =\"" + token[0] + "\" site=\""+ token[1] + "\" datatype=\"" + dataType + "\">\n")

				idx = 1

			if prevHole != token[2] :
				if prevCore != token[3] and prevCore != "" :
					fout.write("\t\t\t</Core>\n")
				if prevHole != "" :
					fout.write("\t\t</Hole>\n")
				fout.write("\t\t<Hole value=\"" + token[2] + "\">\n")

			if prevCore != token[3] :
				if prevCore != "" :
					fout.write("\t\t\t</Core>\n")
				fout.write("\t\t\t<Core id=\"" + token[3] + "\">\n")

			if max_len == 10 :
				temp_token = token[9]
				last = temp_token.find(" ", 0)
				last_token = temp_token[0:last]
				fout.write("\t\t\t\t<Value type=\"" + token[4] + "\" section=\"" + token[5] + "\" top =\"" + token[6]+ "\" bottom =\"" + token[7] + "\" depth=\"" + token[8]+ "\" data=\""+ last_token + "\" />\n")
			elif max_len > 10 and max_len < 13 :
				if token[10][0] == "-" :
					fout.write("\t\t\t\t<Value type=\"" + token[4] + "\" section=\"" + token[5] + "\" top =\"" + token[6]+ "\" bottom =\"" + token[7] + "\" depth=\"" + token[8]+ "\" data=\""+ token[9]+ "\" />\n")
				else :
					temp_token = token[10]
					last = temp_token.find("\n", 0)
					last_token = temp_token[0:last]
					fout.write("\t\t\t\t<Value type=\"" + token[4] + "\" section=\"" + token[5] + "\" top =\"" + token[6]+ "\" bottom =\"" + token[7] + "\" depth=\"" + token[8]+ "\" data=\""+ token[9]+ "\" runno=\""+ last_token + "\" />\n")
			elif max_len >= 13:
				if age_flag == False : 
					if splice_flag == True :
						temp_token = token[13]
						last = temp_token.find("\n", 0)
						last_token = temp_token[0:last]
						fout.write("\t\t\t\t<Value type=\"" + token[4] + "\" section=\"" + token[5] + "\" top =\"" + token[6]+ "\" bottom =\"" + token[7] + "\" depth=\"" + token[8]+ "\" data=\""+ token[9]+ "\" runno=\"" + token[10] + "\" annotation=\""+ token[11] + "\" rawdepth=\""+ token[12] + "\" offset=\""+ last_token+ "\" />\n")
					else :
						temp_token = token[12]
						last = temp_token.find("\n", 0)
						last_token = temp_token[0:last]
						fout.write("\t\t\t\t<Value type=\"" + token[4] + "\" section=\"" + token[5] + "\" top =\"" + token[6]+ "\" bottom =\"" + token[7] + "\" depth=\"" + token[8]+ "\" data=\""+ token[9]+ "\" runno=\"" + token[10] + "\" rawdepth=\""+ token[11] + "\" offset=\""+ last_token+ "\" />\n")
				else :
					temp_token = token[12]
					last = temp_token.find("\n", 0)
					last_token = temp_token[0:last]
					fout.write("\t\t\t\t<Value type=\"" + token[4] + "\" section=\"" + token[5] + "\" top =\"" + token[6]+ "\" bottom =\"" + token[7] + "\" depth=\"" + token[8]+ "\" data=\""+ token[9]+ "\" sedrate=\"" + token[10] + "\" depth2=\""+ token[11] + "\" age=\""+ last_token+ "\" />\n")

			prevHole = token[2]
			prevCore = token[3] 
				
		if prevCore != "" :
			fout.write("\t\t\t</Core>\n")

		if prevHole != "" :
			fout.write("\t\t</Hole>\n")
			fout.write("\t</Data>\n")
		fout.write("</Correlator>\n")
		fout.close()
		fin.close()

	""" Bare-bones validation of image listing files: Count tokens in first non-comment line """
	def ValidateImageListingFile(self, file):
		valid = False
		f = open(file, 'r')
		lines = f.readlines()
		for line in lines[1:]: # skip first line
			if line[0] == '#':
				continue

			# There are two acceptable formats:
			# LIMS format is 11+ tokens with space-separated fields. Columns: expedition site hole
			# core coreType section topOffset bottomOffset depth length image_id
			# Chronos format is 14 tokens with tab-separated fields. Columns: expedition site hole core
			# sectionNumber sectionID sectionType coreType curatedLength linearLength MBSF FORMAT DPI imageURL
			spaceTokens = line.split(' ')
			tabTokens = line.split('\t')
			if len(spaceTokens) >= 11 or len(tabTokens) == 14:
				valid = True
				break

		if not valid:
			self.parent.OnShowMessage("Error", "Invalid image listing file, expected either LIMS or Chronos format", 1)

		return valid


	def OnIMPORT_IMAGE(self):
		opendlg = wx.FileDialog(self, "Open Image Data file", self.parent.Directory, "", wildcard = "*.*")
		ret = opendlg.ShowModal()
		path = opendlg.GetPath()
		source_name = opendlg.GetFilename()
		self.parent.Directory = opendlg.GetDirectory()
		opendlg.Destroy()
		if ret == wx.ID_OK and self.ValidateImageListingFile(path):
			item = self.tree.GetSelection()
			idx = self.tree.GetChildrenCount(item, False)
			parentItem = self.tree.GetItemParent(item)
			title = self.tree.GetItemText(parentItem, 0)
			max = len(title)
			last = title.find("-", 0)
			leg = title[0:last]
			site = title[last+1:max]

		 	tempstamp = str(datetime.today())
			last = tempstamp.find(":", 0)
			last = tempstamp.find(":", last+1)
			#stamp = tempstamp[0:10] + "," + tempstamp[12:16]
			stamp = tempstamp[0:last]

			newline = self.tree.AppendItem(item, "Table")
			self.tree.SetItemText(newline,  "IMAGE", 1)

			filename = str(title) + '.' + str(idx) + '.image.table'
			self.tree.SetItemText(newline,  filename, 8)

			self.tree.SetItemText(newline, "Enable", 2)
			self.tree.SetItemTextColour(newline, wx.BLUE)
			self.tree.SetItemText(newline, stamp, 6)
			self.tree.SetItemText(newline, self.parent.user, 7)
			self.tree.SetItemText(newline, path, 9)
			self.tree.SetItemText(newline, title + '/', 10)

			fullname = self.parent.DBPath +'db/' + title + '/' + filename 
			if sys.platform == 'win32' :
				workingdir = os.getcwd()
				os.chdir(self.parent.Directory)
				cmd = 'copy \"' + source_name + '\" \"' + fullname + '\"'
				os.system(cmd)
				os.chdir(workingdir)
			else :
				cmd = 'cp \"' + path + '\" \"' + fullname + '\"'
				os.system(cmd)

			self.OnUPDATE_DB_FILE(self.tree.GetItemText(parentItem, 0), parentItem)
			self.parent.OnShowMessage("Information", "Successfully imported", 1)


	def IMPORT_TIME_SERIES(self):
		opendlg = wx.FileDialog(self, "Open Time Series file", self.parent.Directory, "", wildcard = "*.*")
		ret = opendlg.ShowModal()
		path = opendlg.GetPath()
		source_name = opendlg.GetFilename()
		self.parent.Directory = opendlg.GetDirectory()
		opendlg.Destroy()
		if ret == wx.ID_OK :
			item = self.tree.GetSelection()
			idx = self.tree.GetChildrenCount(item, False)
			parentItem = self.tree.GetItemParent(item)
			title = self.tree.GetItemText(parentItem, 0)
			max = len(title)
			last = title.find("-", 0)
			leg = title[0:last]
			site = title[last+1:max]

			filename = str(title) + '.' + str(idx) + '.age.model'
			fullname = self.parent.DBPath +'db/' + title + '/' + filename 
			last = path.find(".xml", 0)
			if last >= 0 :
				self.handler.init()
				self.handler.openFile(self.parent.Directory + "/.tmp_table")	
				self.parser.parse(path)
				self.handler.closeFile()
				path = self.parent.Directory + "/.tmp_table"
				source_name = ".tmp_table"
				if self.handler.type != "age model" :
					self.parent.OnShowMessage("Error", "It is not age model", 1)
					return

			if sys.platform == 'win32' :
				workingdir = os.getcwd()
				os.chdir(self.parent.Directory)
				cmd = 'copy \"' + source_name + '\" \"' + fullname + '\"'
				os.system(cmd)
				os.chdir(workingdir)
			else :
				cmd = 'cp \"' + path + '\" \"' + fullname + '\"'
				os.system(cmd)

		 	tempstamp = str(datetime.today())
			last = tempstamp.find(":", 0)
			last = tempstamp.find(":", last+1)
			#stamp = tempstamp[0:10] + "," + tempstamp[12:16]
			stamp = tempstamp[0:last]

			newline = self.tree.AppendItem(item, "Model")
			self.tree.SetItemText(newline,  "AGE", 1)

			self.tree.SetItemText(newline,  filename, 8)

			self.tree.SetItemText(newline, "Enable", 2)
			self.tree.SetItemTextColour(newline, wx.BLUE)
			self.tree.SetItemText(newline, stamp, 6)
			self.tree.SetItemText(newline, self.parent.user, 7)
			self.tree.SetItemText(newline, path, 9)
			self.tree.SetItemText(newline, title + '/', 10)

			self.OnUPDATE_DB_FILE(self.tree.GetItemText(parentItem, 0), parentItem)
			self.parent.OnShowMessage("Information", "Successfully imported", 1)


	def IMPORT_AGE_MODEL(self):
		opendlg = wx.FileDialog(self, "Open Age Model file", self.parent.Directory, "", wildcard = "*.*")
		ret = opendlg.ShowModal()
		path = opendlg.GetPath()
		source_name = opendlg.GetFilename()
		self.parent.Directory = opendlg.GetDirectory()
		opendlg.Destroy()
		if ret == wx.ID_OK :
			item = self.tree.GetSelection()
			idx = self.tree.GetChildrenCount(item, False)
			parentItem = self.tree.GetItemParent(item)
			title = self.tree.GetItemText(parentItem, 0)
			max = len(title)
			last = title.find("-", 0)
			leg = title[0:last]
			site = title[last+1:max]

			filename = str(title) + '.' + str(idx) + '.age-depth.dat'
			fullname = self.parent.DBPath +'db/' + title + '/' + filename 
			last = path.find(".xml", 0)
			if last >= 0 :
				self.handler.init()
				self.handler.openFile(self.parent.Directory + "/.tmp_table")	
				self.parser.parse(path)
				self.handler.closeFile()
				path = self.parent.Directory + "/.tmp_table"
				source_name = ".tmp_table"
				if self.handler.type != "age depth" :
					self.parent.OnShowMessage("Error", "It is not age depth values", 1)
					return

			if sys.platform == 'win32' :
				workingdir = os.getcwd()
				os.chdir(self.parent.Directory)
				cmd = 'copy \"' + source_name + '\" \"' + fullname + '\"'
				os.system(cmd)
				os.chdir(workingdir)
			else :
				cmd = 'cp \"' + path + '\" \"' + fullname + '\"'
				os.system(cmd)

		 	tempstamp = str(datetime.today())
			last = tempstamp.find(":", 0)
			last = tempstamp.find(":", last+1)
			#stamp = tempstamp[0:10] + "," + tempstamp[12:16]
			stamp = tempstamp[0:last]

			newline = self.tree.AppendItem(item, "Value")
			self.tree.SetItemText(newline,  "AGE/DEPTH", 1)

			self.tree.SetItemText(newline,  filename, 8)

			self.tree.SetItemText(newline, "Enable", 2)
			self.tree.SetItemTextColour(newline, wx.BLUE)
			self.tree.SetItemText(newline, stamp, 6)
			self.tree.SetItemText(newline, self.parent.user, 7)
			self.tree.SetItemText(newline, path, 9)
			self.tree.SetItemText(newline, title + '/', 10)

			self.OnUPDATE_DB_FILE(self.tree.GetItemText(parentItem, 0), parentItem)
			self.parent.OnShowMessage("Information", "Successfully imported", 1)


	def OnIMPORT_STRAT(self):
		while True :
			self.OnIMPORT_STRAT1()
			# 1/22/2014 brgtodo: Allow multiple selection to avoid nagging here?
			ret = self.parent.OnShowMessage("About", "Any more stratigraphy files to add now?", 2)
			if ret != wx.ID_OK :
				break

	def ValidateStratFile(self, stratFile, leg, site, title):
		valid = False

		# account for off-chance user selects an app bundle on OSX
		if not os.path.isfile(stratFile):
			self.parent.OnShowMessage("Error", "Invalid file selected", 1)
			return False

		f = open(stratFile, 'r+')
		for line in f :
			max = len(line)
			if max == 1 : 
				continue
				
			modifiedLine = line[0:-1].split()
			if modifiedLine[0] == 'null' :
				continue
			max = len(modifiedLine)
			if max == 1 : 
				modifiedLine = line[0:-1].split('\t')
				max = len(modifiedLine)
			if modifiedLine[max-1] == '\r' :
				max =  max -1
			if max >= 20 :
				if modifiedLine[4] == leg and modifiedLine[5] == site :
					valid = True
				else:
					self.parent.OnShowMessage("Error", "This stratigraphy data is not for " + title , 1)
					break
			else :
				self.parent.OnShowMessage("Error", "Invalid stratigraphy file", 1)
				break

		f.close()
		return valid

	def OnIMPORT_STRAT1(self):
		filterindex = 0
		opendlg = wx.FileDialog(self, "Open Stratigraphy Data file", self.parent.Directory, "", wildcard = "Diatoms|*.*|Radioloria|*.*|Foraminifera|*.*|Nannofossils|*.*|Paleomag|*.*")
		opendlg.SetFilterIndex(filterindex)
		ret = opendlg.ShowModal()
		path = opendlg.GetPath()
		source_name = opendlg.GetFilename()
		self.parent.Directory = opendlg.GetDirectory()
		filterindex = opendlg.GetFilterIndex()
		opendlg.Destroy()
		if ret == wx.ID_OK :
			item = self.tree.GetSelection()
			parentItem = self.tree.GetItemParent(item)
			title = self.tree.GetItemText(parentItem, 0)
			max = len(title)
			last = title.find("-", 0)
			leg = title[0:last]
			site = title[last+1:max]

			if not self.ValidateStratFile(path, leg, site, title):
				return

		 	tempstamp = str(datetime.today())
			last = tempstamp.find(":", 0)
			last = tempstamp.find(":", last+1)
			#stamp = tempstamp[0:10] + "," + tempstamp[12:16]
			stamp = tempstamp[0:last]

			type = "Diatoms" 
			if filterindex == 1 : 
				type =  "Radioloria"
			elif filterindex == 2 : 
				type = "Foraminifera"
			elif filterindex == 3 : 
				type = "Nannofossils"
			elif filterindex == 4 : 
				type = "Paleomag"
			newline = self.tree.AppendItem(item, type)

			filename = self.Set_NAMING(type, title, 'strat')
			self.tree.SetItemText(newline,  filename, 8)

			self.tree.SetItemText(newline, "Enable", 2)
			self.tree.SetItemTextColour(newline, wx.BLUE)
			self.tree.SetItemText(newline, stamp, 6)
			self.tree.SetItemText(newline, self.parent.user, 7)
			self.tree.SetItemText(newline, path, 9)
			self.tree.SetItemText(newline, title + '/', 10)

			fullname = self.parent.DBPath +'db/' + title + '/' + filename 
			if sys.platform == 'win32' :
				workingdir = os.getcwd()
				os.chdir(self.parent.Directory)
				cmd = 'copy \"' + source_name + '\" \"' + fullname + '\"'
				os.system(cmd)
				os.chdir(workingdir)
			else :
				cmd = 'cp \"' + path + '\" \"' + fullname + '\"'
				os.system(cmd)

			self.OnUPDATE_DB_FILE(self.tree.GetItemText(parentItem, 0), parentItem)

			self.parent.OnShowMessage("Information", "Successfully imported", 1)

	# given parent node, return a list of all top-level children to get around the
	# obnoxious "GetFirstChild(), then GetNextChild() for the rest" dance seen
	# throughout this file
	def GetChildren(self, parentNode):
		kids = []
		childNode, cookie = self.tree.GetFirstChild(parentNode)
		while childNode.IsOk():
			kids.append(childNode)
			childNode = self.tree.GetNextSibling(childNode)
		return kids
	
	# given siteRoot list item, return metadata needed to load each of site's hole files (all types):
	# this is necessary to create affine, splice, and ELD tables on the fly
	def GetAllSiteHoles(self, siteRoot):
		holeData = []
		#print "site = {}".format(self.tree.GetItemText(siteRoot, 0))
		kids = self.GetChildren(siteRoot)
		for k in kids:
			nodeName = self.tree.GetItemText(k, 0)
			typeInt, annot = self.parent.TypeStrToInt(nodeName)
			if nodeName not in STD_SITE_NODES:
				#print "found type {}".format(nodeName)
				subkids = self.GetChildren(k)
				for sk in subkids:
					if self.tree.GetItemText(sk, 0) != "-Cull Table":
						# found hole data! make a tuple of metadata required for py_correlator.openHoleFile()
						filename = self.parent.DBPath + "db/" + self.tree.GetItemText(sk, 10) + self.tree.GetItemText(sk, 8)
						decimate = int(self.tree.GetItemText(sk, 3))
						mdTuple = (filename, typeInt, annot, decimate) # full file path, integer data type, annotation (for user type), decimate value
						holeData.append(mdTuple)
		return holeData
	
	def LoadAllHoles(self, siteRoot):
		for hd in self.GetAllSiteHoles(siteRoot):
			py_correlator.openHoleFile(hd[0], -1, hd[1], hd[3], 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, hd[2])
	
	def GetTables(self, siteRoot, tableTypeStr):
		tableData = []
		kids = self.GetChildren(siteRoot)
		for k in kids:
			if self.tree.GetItemText(k, 0) == "Saved Tables":
				subkids = self.GetChildren(k)
				for sk in subkids:
					if self.tree.GetItemText(sk, 1) == tableTypeStr:
						filename = self.tree.GetItemText(sk, 8)
						fullpath = self.parent.DBPath + "db/" + self.tree.GetItemText(sk, 10) + filename
						enabled = True if self.tree.GetItemText(sk, 2) == "Enable" else False
						tuple = (filename, fullpath, enabled)
						tableData.append(tuple)
		return tableData
	
	def GetLogTables(self, siteRoot):
		logTables = []
		enabledLog = None
		for kid in self.GetChildren(siteRoot):
			if self.tree.GetItemText(kid, 0) == "Downhole Log Data":
				for subkid in self.GetChildren(kid):
					filename = self.tree.GetItemText(subkid, 8)
					fullpath = self.parent.DBPath + "db/" + self.tree.GetItemText(subkid, 10) + filename
					dataColumn = int(self.tree.GetItemText(subkid, 11))
					enabled = True if self.tree.GetItemText(subkid, 2) == "Enable" else False
					tuple = (filename, fullpath, dataColumn, enabled)
					if enabledLog is None and enabled:
						enabledLog = tuple
					logTables.append(tuple)
		return logTables, enabledLog
	
	def GetAffineTables(self, siteRoot):
		affineTables = self.GetTables(siteRoot, "AFFINE")
		enabledFilename = None
		for at in affineTables:
			if at[2]:
				enabledFilename = at[0]
				break
		return affineTables, enabledFilename
	
	def GetSpliceTables(self, siteRoot):
		enabledFilename = None
		spliceTables = self.GetTables(siteRoot, "SPLICE")
		for st in spliceTables:
			if st[2]:
				enabledFilename = st[0]
				break
		return spliceTables, enabledFilename

	def ExportAffineTable(self, affineFile, outFile, formatStr):
		if formatStr == "XML":
			self.SAVE_AFFINE_TO_XML(affineFile, outFile)
		else:
			outFile += '.' + formatStr.lower()
			py_correlator.openAttributeFile(affineFile, 0)
			py_correlator.setDelimiter(FormatDict[formatStr])
			#py_correlator.saveAttributeFile(outFile, 1)
			py_correlator.exportAffineFile(outFile)
			py_correlator.setDelimiter(FormatDict["Text"]) # always reset to "internal" file format
			
	def ExportSpliceTable(self, spliceFile, outFile, siteItem):
		doExport = False
		affineTables, curAffine = self.GetAffineTables(siteItem)
		spliceDlg = dialog.ExportSpliceDialog(self, [at[0] for at in affineTables], curAffine)
		if spliceDlg.ShowModal() == wx.ID_OK:
			doExport = True
			formatStr = spliceDlg.GetSelectedFormat() 
			if formatStr == "XML":
				suffix = ".splice.table"
				self.SAVE_SPLICE_TO_XML(spliceFile, outFile + suffix)
			else:
				self.LoadAllHoles(siteItem)
				for at in affineTables:
					if at[0] == spliceDlg.GetSelectedAffine():
						py_correlator.openAttributeFile(at[1], 0)
						break
				suffix = "spliceinterval" if spliceDlg.GetExportSIT() else "splicetie" 
				outFile += '.' + suffix + '.' + formatStr.lower()
				py_correlator.openSpliceFile(spliceFile)
				py_correlator.setDelimiter(FormatDict[formatStr])
				#py_correlator.saveAttributeFile(outFile, 2)
				py_correlator.exportSpliceFile(outFile, spliceDlg.GetExportSIT())
				py_correlator.setDelimiter(FormatDict["Text"])
				
		return doExport
				
	def ExportELDTable(self, eldFile, outFile, siteItem):
		doExport = False
		affineTables, curAffine = self.GetAffineTables(siteItem)
		spliceTables, curSplice = self.GetSpliceTables(siteItem)
		eldDlg = dialog.ExportELDDialog(self, [at[0] for at in affineTables], curAffine, [st[0] for st in spliceTables], curSplice)
		if eldDlg.ShowModal() == wx.ID_OK:
			doExport = True
			formatStr = eldDlg.GetSelectedFormat()
			if formatStr == "XML":
				self.SAVE_ELD_TO_XML(eldFile, outFile)
			else:
				self.LoadAllHoles(siteItem)
				logTables, enabledLog = self.GetLogTables(siteItem)
				if enabledLog is not None:
					py_correlator.openLogFile(enabledLog[1], enabledLog[2])
				for at in affineTables:
					if at[0] == eldDlg.GetSelectedAffine():
						py_correlator.openAttributeFile(at[1], 0)
						break
				for st in spliceTables:
					if st[0] == eldDlg.GetSelectedSplice():
						py_correlator.openSpliceFile(st[1])
						break
				# brgtodo: log file selection?
				outFile += "." + formatStr.lower()
				py_correlator.openAttributeFile(eldFile, 1)
				py_correlator.setDelimiter(FormatDict[formatStr])
				py_correlator.saveAttributeFile(outFile, 4)
				py_correlator.setDelimiter(FormatDict["Text"])

		return doExport
                
	
	# brg 9/9/2014: "Export" affine/splice/ELD etc - just copies internal file to selected location 
	def OnExportSavedTable(self):
		if self.selectedIdx != None :
			opendlg = wx.FileDialog(self, "Select Directory For Export", self.parent.Directory, style=wx.SAVE)
			if opendlg.ShowModal() == wx.ID_OK:
				path = opendlg.GetDirectory()
				filename = opendlg.GetFilename()
				self.parent.Directory = path
				opendlg.Destroy()

				selParentItem = self.tree.GetItemParent(self.selectedIdx)
				siteItem = self.tree.GetItemParent(selParentItem)
				#title = self.tree.GetItemText(siteItem, 0)

				source = self.parent.DBPath + 'db/' + self.tree.GetItemText(self.selectedIdx, 10) + self.tree.GetItemText(self.selectedIdx, 8)
				outfile = filename + ".dat"

				selParentTitle = self.tree.GetItemText(selParentItem, 0) 
				if selParentTitle == "Saved Tables" :
					tableType = self.tree.GetItemText(self.selectedIdx, 1)
					if tableType == "AFFINE" :
						formatDlg = dialog.ExportFormatDialog(self)
						if formatDlg.ShowModal() == wx.ID_OK:
							self.LoadAllHoles(siteItem)
							outAffineFile = filename + ".affine.table"
							self.ExportAffineTable(source, path + '/' + outAffineFile, formatDlg.GetSelectedFormat())
						else:
							return
					elif tableType == "SPLICE":
						if not self.ExportSpliceTable(source, path + '/' + filename, siteItem):
							return
					elif tableType == "ELD" :
						outELDFile = filename + ".eld.table"
						if not self.ExportELDTable(source, path + '/' + outELDFile, siteItem):
							return
				elif selParentItem == "Age Models" :
					tableType = self.tree.GetItemText(self.selectedIdx, 1)
					if tableType == "AGE/DEPTH" :
						outfile = filename + ".age-depth.table"
					elif tableType == "AGE" :
						outfile = filename + ".age.model"
				elif selParentItem == "Image Data" :
					outfile = filename + ".dat"
				else :
					temp_title = self.tree.GetItemText(self.selectedIdx, 0)
					if temp_title == "-Cull Table" :
						outfile = filename + ".cull.table"

				if selParentTitle != "Saved Tables":
					if sys.platform == 'win32' :
						workingdir = os.getcwd()
						# ------------------------
						os.chdir(self.parent.DBPath + 'db\\' + title)
						cmd = 'copy ' + self.tree.GetItemText(self.selectedIdx, 8)  + ' \"' + path + '\\' + str(outfile) + '\"'
						os.system(cmd)
						os.chdir(workingdir)
					else:
						cmd = 'cp \"' +  source  + '\" \"' + path + '/' + outfile + '\"'
						os.system(cmd)
				self.parent.OnShowMessage("Information", "Successfully exported", 1)


	def EXPORT_REPORT(self):
		if self.selectedIdx != None :
			opendlg = wx.DirDialog(self, "Select Directory For Export", self.parent.Directory)
			ret = opendlg.ShowModal()
			path = opendlg.GetPath()
			self.parent.Directory = path
			opendlg.Destroy()
			if ret == wx.ID_OK :
				parentItem = self.tree.GetItemParent(self.selectedIdx)
				outfile = self.tree.GetItemText(self.selectedIdx, 1)

				if sys.platform == 'win32' :
					workingdir = os.getcwd()
					os.chdir(self.parent.DBPath + 'log\\')					
					cmd = 'copy ' +  outfile  + ' \"' + path + '/' + outfile + '\"'
					os.system(cmd)
					os.chdir(workingdir)
				else :	
					source = self.parent.DBPath + 'log/' + self.tree.GetItemText(self.selectedIdx, 1)
					cmd = 'cp \"' +  source  + '\" \"' + path + '/' + outfile + '\"'
					os.system(cmd)
				self.parent.OnShowMessage("Information", "Successfully exported", 1)


	def OnINITGENERICSHEET(self):
		self.dataPanel.SetColLabelValue(0, "Data Type")
		for i in range(1, 39) :
			self.dataPanel.SetColLabelValue(i, "?")


	def OnDELETEALL(self):
		self.parent.OnNewData(None)
		self.tree.DeleteChildren(self.root)
		self.repCount = 0

		if sys.platform == 'win32' :
			# ------- [NEED TO DO] not delete file, move the directory to backup
			workingdir = os.getcwd()
			os.chdir(self.parent.DBPath)
			os.system('rd /s /q db')
			os.system('mkdir db')			
			os.chdir(workingdir)
		else :
			# ------- not delete file, move the directory to backup
			#if os.access(self.parent.DBPath + 'backup/' , os.F_OK) == False :
			#	os.mkdir(self.parent.DBPath + 'backup/')
			#newdirname = '\'' +self.parent.DBPath + 'backup/' + str(datetime.today()) + '/\''
			#os.system('mv ' + self.parent.DBPath + 'db/ ' + newdirname)

			# brg 9/17/2013 above backup directory appears to be a half-implemented feature:
			# reverting to normal file deletion for now.
			os.system('rm -rf ' + self.parent.DBPath + 'db/')
			os.system('mkdir '+ self.parent.DBPath + 'db/')
	
		self.parent.logFileptr.write("Delete All Dataset \n\n")


		log_report = self.tree.AppendItem(self.root, 'Session Reports')
		list = os.listdir(self.parent.DBPath + 'log/')
		for dir in list :
			if dir != ".DS_Store" :
				report_item = self.tree.AppendItem(log_report, 'Report')
				self.tree.SetItemText(report_item, dir, 1)
				last = dir.find(".", 0)
				user = dir[0:last]
				self.tree.SetItemText(report_item, user, 7)
				start = last + 1
				last = dir.find("-", start)
				last = dir.find("-", last+1)
				last = dir.find("-", last+1)
				time = dir[start:last] + " "
				start = last + 1
				last = dir.find("-", start)
				time += dir[start:last] + ":"
				start = last + 1
				last = dir.find(".", start)
				time += dir[start:last]
				self.tree.SetItemText(report_item, time, 6)

		self.parent.Window.UpdateDrawing()


	def OnDELETE(self):
		items = self.tree.GetSelections()
		type = "-"
		title = "-"

		# CHECK CURRNT LOADING ITEM
		if self.selectBackup != None :
			back_type = ""
			back_title = self.title 
			for selectItem in self.selectBackup :
				parentItem = self.tree.GetItemParent(selectItem)
				if self.tree.GetItemText(parentItem, 0) == "Root" :
					back_type = "*"
				elif len(self.tree.GetItemText(selectItem, 8)) > 0 :
					back_type = self.tree.GetItemText(parentItem, 0)
				else :
					back_type = self.tree.GetItemText(selectItem, 0)

			if items != [] :
				for selectItem in items :
					if self.tree.GetItemText(selectItem, 0) != "Root" :
						parentItem = self.tree.GetItemParent(selectItem)
						if self.tree.GetItemText(parentItem, 0) == "Root" :
							type = "*"
							title = self.tree.GetItemText(selectItem, 0)
						elif len(self.tree.GetItemText(selectItem, 8)) > 0 :
							label = self.tree.GetItemText(parentItem, 0)
							if label == "Saved Tables" or label == "Downhole Log Data" or label == "Stratigraphy" or label == "Age Models":
								type = "*"
							else :
								type = self.tree.GetItemText(parentItem, 0)
							parentItem = self.tree.GetItemParent(parentItem)
							title = self.tree.GetItemText(parentItem, 0)
						else :
							type = self.tree.GetItemText(selectItem, 0)
							title = self.tree.GetItemText(parentItem, 0)
					else :
						title = back_title
						type = "*"

			if title == back_title :
				if type == "*" or back_type == "*" or type == back_type :
					ret = self.parent.OnShowMessage("Information", "Loaded Data will be clear.", 2)
					if ret == wx.ID_OK :
						self.parent.OnNewData(None)
						self.selectBackup = []
					else :
						return

		idx = 0
		hole = ""
		level = 2 
		label = ""
		titleItem = None
		for selectItem in items :
			label = self.tree.GetItemText(selectItem, 0)
			
			if label == "Root" :
				if self.tree.GetChildrenCount(selectItem, False) == 0 :
					self.parent.OnShowMessage("Error", "There is no data to delete", 1)
					return

				ret = self.parent.OnShowMessage("About", "Do you want to delete all?", 2)
				if ret == wx.ID_OK :
					self.OnDELETEALL()
					return
				break

			if label == "Saved Tables" :
				self.parent.OnShowMessage("Error", "You can not delete Table", 1)
				break
			if label == "Downhole Log Data" :
				self.parent.OnShowMessage("Error", "You can not delete Log", 1)
				break
			if label == "Stratigraphy" :
				self.parent.OnShowMessage("Error", "You can not delete Stratigraphy", 1)
				break
			if label == "Age Models" :
				self.parent.OnShowMessage("Error", "You can not delete Age Models", 1)
				break
			if label == "Image Data" :
				self.parent.OnShowMessage("Error", "You can not delete Image Data", 1)
				break

			if idx == 0 :
				if label == "Table" :
					label = self.tree.GetItemText(selectItem, 1) + " Table"
				elif label == "Model" :
					label = self.tree.GetItemText(selectItem, 1) + " Model"
				else :
					label = self.tree.GetItemText(selectItem, 1)

				ret = self.parent.OnShowMessage("About", "Do you want to delete " + label + "?", 2)
				if ret == wx.ID_OK :
					idx = 1
				else :
					return

			parentItem = self.tree.GetItemParent(selectItem)

			if len(self.tree.GetItemText(selectItem, 8)) > 0 :
				
				hole = self.tree.GetItemText(selectItem, 0)
				type = self.tree.GetItemText(parentItem, 0)
				titleItem = self.tree.GetItemParent(parentItem)
				title = self.tree.GetItemText(titleItem, 0)

				if type == 'Saved Tables' :
					type = self.tree.GetItemText(selectItem, 1) 
					hole = self.tree.GetItemText(selectItem, 8)
					if type == "-Cull Table" :
						start = hole.find('.', 0)
						self.UpdateRANGE(hole[0:start], titleItem)
					level = 0 
				elif type == 'Downhole Log Data' :
					level = 0 
					hole = self.tree.GetItemText(selectItem, 8)
				elif type == 'Stratigraphy' :
					level = 0 
					hole = self.tree.GetItemText(selectItem, 8)
				elif type == 'Age Models' :
					level = 0 
					hole = self.tree.GetItemText(selectItem, 8)
				elif type == 'Image Data' :
					level = 0 
					hole = self.tree.GetItemText(selectItem, 8)
				else :
					level = 2 

				if hole == '-Cull Table' :
					type = hole
					hole = self.tree.GetItemText(selectItem, 8)
					# NEED TO SET
					#start = hole.find('.', 0)
					#self.UpdateRANGE(hole[0:start], titleItem)
				
				if sys.platform == 'win32' :
					filename = self.tree.GetItemText(selectItem, 8)
					workingdir = os.getcwd()
					os.chdir(self.parent.DBPath + 'db/' + title + '/')
					os.system('del \"' + filename + '\"')
					os.chdir(workingdir)
					self.parent.logFileptr.write("Delete " + filename + "\n\n")
				else :
					filename = self.parent.DBPath + 'db/' + title + '/' + self.tree.GetItemText(selectItem, 8)
					#  --- not to delete
					os.system('rm \"'+ filename + '\"')
					if "affine" in filename:
						iodpFilename = filename + "_IODP"
						os.system('rm \"' + iodpFilename + '\"')
					self.parent.logFileptr.write("Delete " + filename + "\n\n")
			else :
				type = self.tree.GetItemText(selectItem, 0)
				if type.find("-", 0) == -1 :
					title = self.tree.GetItemText(parentItem, 0)
					titleItem = parentItem
					hole = '*'
					level = 1 
					# data type
					totalcount = self.tree.GetChildrenCount(selectItem, False)
					if totalcount > 0 :
						child = self.tree.GetFirstChild(selectItem)
						child_item = child[0]
						if sys.platform == 'win32' :
							filename = self.tree.GetItemText(child_item, 8)
							workingdir = os.getcwd()
							os.chdir(self.parent.DBPath + 'db/' + title + '/')
							os.system('del \"' + filename + '\"')
							os.chdir(workingdir)
							self.parent.logFileptr.write("Delete " + filename + "\n\n")
						else :
							filename = self.parent.DBPath + 'db/' + title + '/' + self.tree.GetItemText(child_item, 8)
							# ----- not to delete
							os.system('rm \"'+ filename + '\"')
							self.parent.logFileptr.write("Delete " + filename + "\n\n")
						for k in range(1, totalcount) :
							child_item = self.tree.GetNextSibling(child_item)
							if sys.platform == 'win32' :
								filename = self.tree.GetItemText(child_item, 8)
								workingdir = os.getcwd()
								os.chdir(self.parent.DBPath + 'db/' + title + '/')
								os.system('del \"' + filename + '\"')
								os.chdir(workingdir)
								self.parent.logFileptr.write("Delete " + filename + "\n\n")
							else :
								filename = self.parent.DBPath + 'db/' + title + '/' + self.tree.GetItemText(child_item, 8)
								# ----- not to delete
								os.system('rm \"'+ filename + '\"')
								self.parent.logFileptr.write("Delete " + filename + "\n\n")

				else : # delete site
					titleItem = selectItem
					title = type
					type = '*' 
					hole = '*'
					level = 0 
					# whole leg-site Directory
					if sys.platform == 'win32' :
						workingdir = os.getcwd()
						os.chdir(self.parent.DBPath + 'db/')
						os.system('rd /s /q ' + title)
						os.chdir(workingdir)
						self.parent.logFileptr.write("Delete " + self.parent.DBPath + 'db/' + title + "\n\n")
					else :
						# ----- not to delete
						os.system('rm -rf ' + self.parent.DBPath + 'db/' + title)
						self.parent.logFileptr.write("Delete " + self.parent.DBPath + 'db/' + title + "\n\n")


			#self.OnSAVE_DB_FILE(title, type, hole)
			self.tree.Delete(selectItem)

			filename = self.parent.DBPath + 'db/' + title + '/datalist.db'
			if os.access(filename, os.F_OK) == True :
				self.OnUPDATE_DB_FILE(title, titleItem)

			if level == 1 :
				totalcount = self.tree.GetChildrenCount(parentItem, False)
				if totalcount == 5 :
					empty_flag = True 
					selectItem = parentItem
					child = self.tree.GetFirstChild(selectItem)
					child_item = child[0]
					if self.tree.GetChildrenCount(child_item, False) > 0 :
						empty_flag = False 
					else :
						for k in range(1, totalcount) :
							child_item = self.tree.GetNextSibling(child_item)
							if self.tree.GetChildrenCount(child_item, False) > 0 :
								empty_flag = False 
								break
					if empty_flag == True :	
						parentItem = self.tree.GetItemParent(selectItem)
						self.tree.Delete(selectItem)
						self.OnSAVE_DB_FILE(title, "*", "*")
			elif level == 2 :
				totalcount = self.tree.GetChildrenCount(parentItem, False)
				if totalcount == 0 :
					selectItem = parentItem
					parentItem = self.tree.GetItemParent(selectItem)
					self.tree.Delete(selectItem)

					totalcount = self.tree.GetChildrenCount(parentItem, False)
					if totalcount == 5 :
						empty_flag = True 
						selectItem = parentItem
						child = self.tree.GetFirstChild(selectItem)
						child_item = child[0]
						if self.tree.GetChildrenCount(child_item, False) > 0 :
							empty_flag = False 
						else :
							for k in range(1, totalcount) :
								child_item = self.tree.GetNextSibling(child_item)
								if self.tree.GetChildrenCount(child_item, False) > 0 :
									empty_flag = False 
									break
						if empty_flag == True :	
							parentItem = self.tree.GetItemParent(selectItem)
							self.tree.Delete(selectItem)
							self.OnSAVE_DB_FILE(title, "*", "*")


	def OnSAVE_DB_FILE(self, title, type, hole):

		filename = self.parent.DBPath + 'db/' + title + '/datalist.db'

		if type == '*' :
 			if sys.platform == 'win32' :
				workingdir = os.getcwd()
				os.chdir(self.parent.DBPath + 'db\\' + title)
				cmd = 'del datalist.db'
				os.chdir(workingdir)				
			else :	
				# delete
				cmd = 'rm \"' + filename + '\"'
				os.system(cmd)

			filename = self.parent.DBPath +'db/datalist.db'
			fin = open(filename, 'r+')
			fout = open(filename + '.temp', 'w+')
			for sub_line in fin :
				lines = sub_line.splitlines()
				for line in lines :
					if line != title :
						fout.write('\n' + line)
			fout.close()
			fin.close()

 			if sys.platform == 'win32' :
 				workingdir = os.getcwd()
 				os.chdir(self.parent.DBPath + 'db')
 		 		os.system('del datalist.db')	
				cmd = 'copy datalist.db.temp datalist.db'
				os.system(cmd)
				os.chdir(workingdir)
			else :				
				cmd = 'mv \"' + filename+'.temp\" \"' + filename  + '\"'
				os.system(cmd)
			
			return

		fin = open(filename, 'r+')
		fout = open(filename+'.temp', 'w+')

		hole_f = ""
		type_f = ""

		write_flag = True 
		for sub_line in fin :
			lines = sub_line.splitlines()
			for line in lines :
				token = line.split(': ')
				if token[0] == "hole" :
					hole_f = token[1]
				elif token[0] == "type" :
					type_f = token[1]
					if hole == hole_f and type == type_f :
						write_flag = False
					elif hole == '*' and type == type_f :
						write_flag = False
					else :
						write_flag = True
						s = 'hole: ' + hole_f + '\ntype: ' + type_f + '\n'
						fout.write(s)
					hole_f = ""
					type_f = ""
				elif token[0] == "culltable" :
					if type == '-Cull Table' and hole == token[1] : 
						print "[DEBUG] > skipped cull"
					else :
						fout.write(line + '\n')
				elif token[0] == "strat" :
					if type == 'Stratigraphy' and hole == token[2] : 
						print "[DEBUG] > skipped strat"
					else :
						fout.write(line + '\n')
				elif token[0] == "age" :
					if type == 'Age Models' and hole == token[1] : 
						print "[DEBUG] > skipped age"
					else :
						fout.write(line + '\n')
				elif token[0] == "image" :
					if type == 'Image Data' and hole == token[1] : 
						print "[DEBUG] > skipped image table"
					else :
						fout.write(line + '\n')
				elif token[0] == "affinetable" :
					if type == 'AFFINE' and hole == token[1] : 
						print "[DEBUG] > skipped affine table"
					else :
						fout.write(line + '\n')
				elif token[0] == "splicetable" :
					if type == 'SPLICE' and hole == token[1] : 
						print "[DEBUG] > skipped splice"
					else :
						fout.write(line + '\n')
				elif token[0] == "eldtable" :
					if type == 'ELD' and hole == token[1] : 
						print "[DEBUG] > skipped eld"
					else :
						fout.write(line + '\n')
				elif token[0] == "log" :
					if type == 'Downhole Log Data' and hole == token[1] : 
						print "[DEBUG] > skipped log"
					else :
						fout.write(line + '\n')
				else :
					if write_flag == True :
						fout.write(line + '\n')

		fout.close()
		fin.close()

		
 		if sys.platform == 'win32' :
 			workingdir = os.getcwd()
 			os.chdir(self.parent.DBPath + 'db\\' + title)
 		 	os.system('del datalist.db')	
			cmd = 'rename datalist.db.temp datalist.db'
			os.system(cmd)
			os.chdir(workingdir)
		else :	
			cmd = 'mv \"' + filename+'.temp\" \"' + filename  + '\"'
			os.system(cmd)
		

	def OnGET_IMAGE_FILENAME(self):
		parentItem = self.tree.GetItemParent(self.propertyIdx)
		title = self.tree.GetItemText(parentItem, 0) 
		child = self.FindItem(parentItem, 'Image Data')
		filename = []
		path = self.parent.DBPath
 		if sys.platform == 'win32' :
			path += '\\db\\' 
		else :
			path += 'db/' 

		if child[0] == True :
			selectItem = child[1]
			totalcount = self.tree.GetChildrenCount(selectItem, False) 
			if totalcount > 0 :
				child = self.tree.GetFirstChild(selectItem)
				child_item = child[0]
 				if sys.platform == 'win32' :
					filename.append(path + title + '\\' + self.tree.GetItemText(child_item, 8))
				else :
					filename.append(path + title + '/' + self.tree.GetItemText(child_item, 8))
				for k in range(1, totalcount) :
					child_item = self.tree.GetNextSibling(child_item)
 					if sys.platform == 'win32' :
						filename.append(path + title + '\\' + self.tree.GetItemText(child_item, 8))
					else :
						filename.append(path + title + '/' + self.tree.GetItemText(child_item, 8))
		return filename


	def OnSAVE_SERIES(self, updatefile):
		parentItem = self.tree.GetItemParent(self.propertyIdx)
		title = self.tree.GetItemText(parentItem, 0) 
		child = self.FindItem(parentItem, 'Age Models')
		filename = ""
		path = self.parent.DBPath + 'db/' + title + '/'
		if child[0] == True :
			selectItem = child[1]

			idx = self.tree.GetChildrenCount(selectItem, False) 
			if idx != 0  and updatefile == True : 
				child = self.tree.GetFirstChild(selectItem)
				child_item = child[0]
				if self.tree.GetItemText(child_item, 2) == "Enable" :
					filename = self.tree.GetItemText(child_item, 8)
				else :
					for k in range(1, totalcount) :
						child_item = self.tree.GetNextSibling(child_item)
						if self.tree.GetItemText(child_item, 2) == "Enable" :
							filename = self.tree.GetItemText(child_item, 8)
							break
			else :	
				filename = title + "." + str(idx) + ".age-depth.dat"
				age_child = self.tree.AppendItem(selectItem, 'Value')
				self.tree.SetItemText(age_child, "AGE/DEPTH", 1)
				self.tree.SetItemText(age_child, "Enable", 2)
				self.tree.SetItemTextColour(age_child, wx.BLUE)

				self.tree.SetItemText(age_child, filename, 8)
				self.tree.SetItemText(age_child, title + '/', 10)

				tempstamp = str(datetime.today())
				last = tempstamp.find(":", 0)
				last = tempstamp.find(":", last+1)
				#stamp = tempstamp[0:10] + "," + tempstamp[12:16]
				stamp = tempstamp[0:last]
				self.tree.SetItemText(age_child, stamp, 6)
				self.tree.SetItemText(age_child, self.parent.user, 7)


		ageFile = open(path+ filename, "w+")
		#ageFile.write("# Mbsf, Mcd, Eld, Age, Sediment rate, Age datum name, Label, type\n")
		ageFile.write("# Depth	Age	Control Point Comment\n")
		ageFile.write("# Generated By Correlator\n")
		s = "# " + str(datetime.today()) + "\n"
		ageFile.write(s)

		sedrate = 0.0
		for data in self.parent.Window.AgeDataList :
			idx, start, rawstart, age, name, label, type, sed = data
			sedrate = sed
			break

		#s = str(self.parent.Window.firstPntDepth) + " \t" + str(self.parent.Window.firstPntDepth) + " \t" + str(self.parent.Window.firstPntDepth) + " \t" +  str(self.parent.Window.firstPntAge) + " \t" + str(sedrate) + " \thandpick \tX \tHandpick\n"
		s = str(self.parent.Window.firstPntDepth) + " \t" +  str(self.parent.Window.firstPntAge) + " \tX Handpick\n"
		ageFile.write(s)

		typename = "" 
		count = 0
		s1 = ""
		s2 = ""
		for data in self.parent.Window.AgeDataList :
			idx, start, rawstart, age, name, label, type, sed = data
			if type == 0 :  #DIATOMS
				typename = "Diatoms"
			elif type == 1 : #RADIOLARIA
				typename = "Radiolaria"
			elif type == 2 : #FORAMINIFERA
				typename = "Foraminifera"
			elif type == 3 : #NANNOFOSSILS
				typename = "Nannofossils"
			elif type == 4 : #PALEOMAG
				typename = "Paleomag"
			else :
				typename = "HandPick"

			s = str(rawstart) + " \t" + str(age) + " \t" + label + " " +  typename + "\n"
			ageFile.write(s)

			#if count == 0 :
			#	s1 = str(rawstart) + " \t" + str(start) + " \t" + str(start) + " \t" + str(age) + " \t"
			#	s2 = name + " \t" + label + " \t" +  typename + "\n"
			#	count = 1
			#else :
			#	s = s1 + str(sed) + " \t" + s2
			#	ageFile.write(s)
			#	s1 = str(rawstart) + " \t" + str(start) + " \t" + str(start) + " \t" + str(age) + " \t"
			#	s2 = name + " \t" + label + " \t" +  typename + "\n"
			#sedrate = sed

		#if len(self.parent.Window.AgeDataList) > 0 :
		#	s = s1 + str(sedrate) + " \t" + s2
		#	ageFile.write(s)

		ageFile.close()
		self.OnUPDATE_DB_FILE(title, parentItem)
		self.parent.TimeChange = False

		return filename
		#idx = 0
		#for data in self.Window.AgeDataList :
		#	py_correlator.setAgeOrder(idx, data[2], data[4])
		#	idx = idx + 1
		#py_correlator.saveAttributeFile(path, 6)


	def OnSAVE_AGES(self, updatefile, importflag):
		if len(self.parent.Window.UserdefStratData) == 0:
			self.parent.OnShowMessage("Error", "There is no userdefined age datum", 1)
			return
			
		items = []
		if importflag == False :
			items = self.selectBackup
		else :
			items = self.tree.GetSelections()
		self.Update_PROPERTY_ITEM(items)
		property = self.propertyIdx
		parentItem = self.tree.GetItemParent(property)
		title = self.tree.GetItemText(parentItem, 0) 
		child = self.FindItem(parentItem, 'Age Models')
		filename = ""
		path = self.parent.DBPath + 'db/' + title + '/'
		if child[0] == True :
			selectItem = child[1]

			idx = 0
			count = 0
			enable_count = 0
			total = self.tree.GetChildrenCount(selectItem, False) 
			if total > 0 : 
				child = self.tree.GetFirstChild(selectItem)
				child_item = child[0]
				if self.tree.GetItemText(child_item, 0) == "Value" and self.tree.GetItemText(child_item, 2) == "Enable" :
					enable_count += 1
					filename = self.tree.GetItemText(child_item, 8)
				if self.tree.GetItemText(child_item, 0) == "Value" :
					count += 1
					str_temp = self.tree.GetItemText(child_item, 8)
					start = str_temp.find(".", 0) + 1
					last = str_temp.find(".", start)
					num = int(str_temp[start:last])
					if idx < num :
						idx = num
				for k in range(1, total) :
					child_item = self.tree.GetNextSibling(child_item)
					if filename == "" and self.tree.GetItemText(child_item, 0) == "Value" and self.tree.GetItemText(child_item, 2) == "Enable" :
						enable_count += 1
						filename = self.tree.GetItemText(child_item, 8)
					if self.tree.GetItemText(child_item, 0) == "Value" :
						count += 1
						str_temp = self.tree.GetItemText(child_item, 8)
						start = str_temp.find(".", 0) + 1
						last = str_temp.find(".", start)
						num = int(str_temp[start:last])
						if idx < num :
							idx = num

			if count > 0 :
				idx += 1
			if updatefile == False or count == 0 or enable_count == 0 : 
				filename = title + "." + str(idx) + ".age-depth.dat"
				age_child = self.tree.AppendItem(selectItem, 'Value')
				self.tree.SetItemText(age_child, "AGE/DEPTH", 1)
				self.tree.SetItemText(age_child, "Enable", 2)
				self.tree.SetItemTextColour(age_child, wx.BLUE)

				self.tree.SetItemText(age_child, filename, 8)
				self.tree.SetItemText(age_child, title + '/', 10)

				tempstamp = str(datetime.today())
				last = tempstamp.find(":", 0)
				last = tempstamp.find(":", last+1)
				#stamp = tempstamp[0:10] + "," + tempstamp[12:16]
				stamp = tempstamp[0:last]
				self.tree.SetItemText(age_child, stamp, 6)
				self.tree.SetItemText(age_child, self.parent.user, 7)


		ageFile = open(path+ filename, "w+")
		ageFile.write("# Depth	Age	Control Point Comment\n")
		ageFile.write("# Generated By Correlator\n")
		s = "# " + str(datetime.today()) + "\n"
		ageFile.write(s)

		#for data in self.parent.Window.StratData :
		#	for r in data :
		#		order, hole, name, label, start, stop, rawstart, rawstop, age, type = r
		#		s = str(rawstart) + " \t" + str(age) + " \t" + label + " " +  name + "\n"
		#		ageFile.write(s)
		for data in self.parent.Window.UserdefStratData :
			for r in data :
				name, start, rawstart, age, comment = r
				if comment == "" or comment == " " :
					comment = "Handpick"

				s = str(rawstart) + " \t" + str(age) + " \t" + name + " " + comment + "\n"
				ageFile.write(s)

		ageFile.close()
		self.OnUPDATE_DB_FILE(title, parentItem)
		self.parent.AgeChange = False

		return filename


	def OnSAVE_SERIES(self, updatefile, importflag):
		items = []
		if importflag == False :
			items = self.selectBackup
		else :
			items = self.tree.GetSelections()
		self.Update_PROPERTY_ITEM(items)
		property = self.propertyIdx
		parentItem = self.tree.GetItemParent(property)
		title = self.tree.GetItemText(parentItem, 0) 
		max =  len(title)
		last = title.find("-", 0)
		leg = title[0:last]
		site = title[last+1:max]

		child = self.FindItem(parentItem, 'Age Models')
		filename = ""
		path = self.parent.DBPath + 'db/' + title + '/'
		if child[0] == True :
			selectItem = child[1]

			idx = 0
			count = 0
			enable_count = 0
			total = self.tree.GetChildrenCount(selectItem, False) 
			if total > 0 : 
				child = self.tree.GetFirstChild(selectItem)
				child_item = child[0]
				if self.tree.GetItemText(child_item, 0) == "Model" and self.tree.GetItemText(child_item, 2) == "Enable" :
					enable_count += 1
					filename = self.tree.GetItemText(child_item, 8)
				if self.tree.GetItemText(child_item, 0) == "Model" :
					count += 1
					str_temp = self.tree.GetItemText(child_item, 8)
					start = str_temp.find(".", 0) + 1
					last = str_temp.find(".", start)
					num = int(str_temp[start:last])
					if idx < num :
						idx = num
				for k in range(1, total) :
					child_item = self.tree.GetNextSibling(child_item)
					if filename == "" and self.tree.GetItemText(child_item, 0) == "Model" and self.tree.GetItemText(child_item, 2) == "Enable" :
						enable_count += 1
						filename = self.tree.GetItemText(child_item, 8)
					if self.tree.GetItemText(child_item, 0) == "Model" :
						count += 1
						str_temp = self.tree.GetItemText(child_item, 8)
						start = str_temp.find(".", 0) + 1
						last = str_temp.find(".", start)
						num = int(str_temp[start:last])
						if idx < num :
							idx = num

			if count > 0 :
				idx += 1
			if updatefile == False or count == 0 or enable_count == 0 : 
				filename = title + "." + str(idx) + ".age.model"
				age_child = self.tree.AppendItem(selectItem, 'Model')
				self.tree.SetItemText(age_child, "AGE", 1)
				self.tree.SetItemText(age_child, "Enable", 2)
				self.tree.SetItemTextColour(age_child, wx.BLUE)

				self.tree.SetItemText(age_child, filename, 8)
				self.tree.SetItemText(age_child, title + '/', 10)

				tempstamp = str(datetime.today())
				last = tempstamp.find(":", 0)
				last = tempstamp.find(":", last+1)
				#stamp = tempstamp[0:10] + "," + tempstamp[12:16]
				stamp = tempstamp[0:last]
				self.tree.SetItemText(age_child, stamp, 6)
				self.tree.SetItemText(age_child, self.parent.user, 7)


		ageFile = open(path+ filename, "w+")
		#ageFile.write("# Mbsf, Mcd, Eld, Age, Sediment rate, Age datum name, Label, type\n")
		#ageFile.write("# mbsf  mcd eld    Age   Data_Value    Sed Rates \n")
		ageFile.write("# Leg, Site, Mbsf, Mcd, Eld, Age, Sediment Rate, Age Datum, Comment, Type \n")
		ageFile.write("# Generated By Correlator\n")
		s = "# " + str(datetime.today()) + "\n"
		ageFile.write(s)

		sedrate = 0.0
		for data in self.parent.Window.AgeDataList :
			idx, start, rawstart, age, name, label, type, sed = data
			sedrate = sed
			break

		s = str(leg) + " \t" + str(site) + " \t" + str(self.parent.Window.firstPntDepth) + " \t" + str(self.parent.Window.firstPntDepth) + " \t" + str(self.parent.Window.firstPntDepth) + " \t" +  str(self.parent.Window.firstPntAge) + " \t" + str(sedrate) + " \tHandpick \tX \tHandpick\n"
		ageFile.write(s)

		typename = "" 
		count = 0
		s1 = ""
		s2 = ""
		for data in self.parent.Window.AgeDataList :
			idx, start, rawstart, age, name, label, type, sed = data
			if type == 0 :  #DIATOMS
				typename = "Diatoms"
			elif type == 1 : #RADIOLARIA
				typename = "Radiolaria"
			elif type == 2 : #FORAMINIFERA
				typename = "Foraminifera"
			elif type == 3 : #NANNOFOSSILS
				typename = "Nannofossils"
			elif type == 4 : #PALEOMAG
				typename = "Paleomag"
			else :
				typename = "Handpick"

			if count == 0 :
				s1 = str(leg) + " \t" + str(site) + " \t" + str(rawstart) + " \t" + str(start) + " \t" + str(start) + " \t" + str(age) + " \t"
				s2 = " \t" + name + " \t" + label + " \t" + typename  
				count = 1
			else :
				s = s1 + str(sed) + s2 + "\n"
				ageFile.write(s)
				s1 = str(leg) + " \t" + str(site) + " \t" + str(rawstart) + " \t" + str(start) + " \t" + str(start) + " \t" + str(age) + " \t"
				s2 = " \t" + name + " \t" + label + " \t" + typename  

			sedrate = sed

		if len(self.parent.Window.AgeDataList) > 0 :
			s = s1 + str(sedrate) + s2 + "\n"
			ageFile.write(s)

		ageFile.close()
		self.OnUPDATE_DB_FILE(title, parentItem)
		self.parent.TimeChange = False

		return filename
		#idx = 0
		#for data in self.Window.AgeDataList :
		#	py_correlator.setAgeOrder(idx, data[2], data[4])
		#	idx = idx + 1
		#py_correlator.saveAttributeFile(path, 6)


	def OnSAVE_DB_ITEM(self, db_f, type, item, source_filename):
		holename = self.tree.GetItemText(item, 0)

		if holename == "-Cull Table" :
			if source_filename == "" :
				source_filename = "-"
			s = '\nculltable: ' + self.tree.GetItemText(item, 8) + ': ' + self.tree.GetItemText(item, 6) + ': ' + self.tree.GetItemText(item, 7) + ': ' + self.tree.GetItemText(item, 2) + ': ' + source_filename  + '\n'
			db_f.write(s)
			return

		s = '\nhole: ' + holename + '\n'
		db_f.write(s)
		s = 'type: ' + type + '\n'
		db_f.write(s)
		s = 'dataName: ' + self.tree.GetItemText(item, 1) + '\n'
		db_f.write(s)
		s = 'depth: ' + self.tree.GetItemText(item, 13) + '\n'
		db_f.write(s)
		s = 'decimate: ' + self.tree.GetItemText(item, 3) + '\n'
		db_f.write(s)
		s = 'min: ' + self.tree.GetItemText(item, 4) + '\n'
		db_f.write(s)
		s = 'max: ' + self.tree.GetItemText(item, 5) + '\n'
		db_f.write(s)
		s = 'file: ' + self.tree.GetItemText(item, 8) + '\n'
		db_f.write(s)
		s = 'source: ' + self.tree.GetItemText(item, 9) + '\n'
		db_f.write(s)
		s = 'data: ' + self.tree.GetItemText(item, 11) + '\n'
		db_f.write(s)
		s = 'enable: ' + self.tree.GetItemText(item, 2) + '\n'
		db_f.write(s)
		s = 'updatedTime: ' + self.tree.GetItemText(item, 6) + '\n'
		db_f.write(s)
		s = 'byWhom: ' + self.tree.GetItemText(item, 7) + '\n'
		db_f.write(s)


	def OnUPDATE_DB_FILE(self, title, parentItem):
		filename = self.parent.DBPath + 'db/' + title + '/datalist.db'

		fout = open(filename, 'w+')
		type = ""

		total = self.tree.GetChildrenCount(parentItem, False)
		if total > 0 :
			child = self.tree.GetFirstChild(parentItem)
			selectItem = child[0]
			type = self.tree.GetItemText(selectItem, 0)

			if type == "Saved Tables"  :
				totalcount = self.tree.GetChildrenCount(selectItem, False)
				if totalcount > 0 :
					child = self.tree.GetFirstChild(selectItem)
					child_item = child[0]
					source_filename =  self.tree.GetItemText(child_item, 9)
					if source_filename == "" :
						source_filename = "-"
					if "AFFINE" == self.tree.GetItemText(child_item, 1) :
						s = '\naffinetable: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 2) + ': ' + source_filename + '\n'
						fout.write(s)
					elif "SPLICE" == self.tree.GetItemText(child_item, 1) :
						s = '\nsplicetable: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 2) + ': ' + source_filename + '\n'
						fout.write(s)
					elif "ELD" == self.tree.GetItemText(child_item, 1) :
						s = '\neldtable: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 2) + ': ' + source_filename + '\n'
						fout.write(s)
					elif "CULL" == self.tree.GetItemText(child_item, 1) :
						s = '\nuni_culltable: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 2) + ': ' + source_filename +  '\n'
						fout.write(s)

					for l in range(1, totalcount) :
						child_item = self.tree.GetNextSibling(child_item)
						source_filename =  self.tree.GetItemText(child_item, 9)
						if source_filename == "" :
							source_filename = "-"
						if "AFFINE" == self.tree.GetItemText(child_item, 1) :
							s = '\naffinetable: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 2) + ': ' + source_filename + '\n'
							fout.write(s)
						elif "SPLICE" == self.tree.GetItemText(child_item, 1) :
							s = '\nsplicetable: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 2) + ': ' + source_filename + '\n'
							fout.write(s)
						elif "ELD" == self.tree.GetItemText(child_item, 1) :
							s = '\neldtable: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 2) + ': ' + source_filename + '\n'
							fout.write(s)
						elif "CULL" == self.tree.GetItemText(child_item, 1) :
							s = '\nuni_culltable: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 2) + ': ' + source_filename + '\n'
							fout.write(s)
			elif type == "Downhole Log Data"  :
				totalcount = self.tree.GetChildrenCount(selectItem, False)
				if totalcount > 0 :
					child = self.tree.GetFirstChild(selectItem)
					child_item = child[0]
					s = '\nlog: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 9) + ': ' +  self.tree.GetItemText(child_item, 11) + ': ' + self.tree.GetItemText(child_item, 2) + ': ' + self.tree.GetItemText(child_item, 1) + ': ' + self.tree.GetItemText(child_item, 4) + ': ' + self.tree.GetItemText(child_item, 5) + ': ' + self.tree.GetItemText(child_item, 3) + ': ' + self.tree.GetItemText(child_item, 12) + '\n'
					fout.write(s)
					for l in range(1, totalcount) :
						child_item = self.tree.GetNextSibling(child_item)
						s = '\nlog: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 9) + ': ' +  self.tree.GetItemText(child_item, 11) + ': ' + self.tree.GetItemText(child_item, 2) + ': ' + self.tree.GetItemText(child_item, 1) + ': ' + self.tree.GetItemText(child_item, 4) + ': ' + self.tree.GetItemText(child_item, 5) + ': ' + self.tree.GetItemText(child_item, 3) + ': ' + self.tree.GetItemText(child_item, 12) + '\n'
						fout.write(s)
			elif type == "Stratigraphy" :
				totalcount = self.tree.GetChildrenCount(selectItem, False)
				if totalcount > 0 :
					child = self.tree.GetFirstChild(selectItem)
					child_item = child[0]
					s = '\nstrat: ' + self.tree.GetItemText(child_item, 0) + ': ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 9) + ': ' + self.tree.GetItemText(child_item, 2) + '\n'
					fout.write(s)
					for l in range(1, totalcount) :
						child_item = self.tree.GetNextSibling(child_item)
						s = '\nstrat: ' + self.tree.GetItemText(child_item, 0) + ': ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 9) + ': ' + self.tree.GetItemText(child_item, 2) + '\n'
						fout.write(s)
			elif type == "Age Models" :
				totalcount = self.tree.GetChildrenCount(selectItem, False)
				if totalcount > 0 :
					child = self.tree.GetFirstChild(selectItem)
					child_item = child[0]
					if "Value" == self.tree.GetItemText(child_item, 0) :
						s = '\nage: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 9) + ': ' + self.tree.GetItemText(child_item, 2) + '\n'
						fout.write(s)
					else :
						s = '\nseries: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 9) + ': ' + self.tree.GetItemText(child_item, 2) + '\n'
						fout.write(s)
					for l in range(1, totalcount) :
						child_item = self.tree.GetNextSibling(child_item)
						if "Value" == self.tree.GetItemText(child_item, 0) :
							s = '\nage: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 9) + ': ' + self.tree.GetItemText(child_item, 2) + '\n'
							fout.write(s)
						else :
							s = '\nseries: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 9) + ': ' + self.tree.GetItemText(child_item, 2) + '\n'
							fout.write(s)
			elif type == "Image Data" :
				totalcount = self.tree.GetChildrenCount(selectItem, False)
				if totalcount > 0 :
					child = self.tree.GetFirstChild(selectItem)
					child_item = child[0]
					s = '\nimage: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 9) + ': ' + self.tree.GetItemText(child_item, 2) + '\n'
					fout.write(s)
					for l in range(1, totalcount) :
						child_item = self.tree.GetNextSibling(child_item)
						s = '\nimage: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 9) + ': ' + self.tree.GetItemText(child_item, 2) + '\n'
						fout.write(s)
			elif type == "Section Summary":
				secsumm_name = self.tree.GetItemText(selectItem, 1)
				if secsumm_name != "":
					fout.write('\nsecsumm: ' + secsumm_name + '\n')
			else :  
				totalcount = self.tree.GetChildrenCount(selectItem, False)
				culltable_item = None
				if totalcount > 0 :
					child = self.tree.GetFirstChild(selectItem)
					child_item = child[0]

					if self.tree.GetItemText(child_item, 0) == "-Cull Table" :
						culltable_item = child_item
					else :
						self.OnSAVE_DB_ITEM(fout, type, child_item, "")
						if len(self.tree.GetItemText(selectItem, 1)) == 0 :
							s = 'typeData: Continuous\n'
							fout.write(s)
						else :
							s = 'typeData: ' + self.tree.GetItemText(selectItem, 1) + '\n'
							fout.write(s)
						s = 'typeDecimate: ' + self.tree.GetItemText(selectItem, 3) + '\n'
						fout.write(s)
						if self.tree.GetItemText(selectItem, 12) != "" :
							s = 'typeSmooth: ' + self.tree.GetItemText(selectItem, 12) + '\n'
							fout.write(s)
						s = 'typeMin: ' + self.tree.GetItemText(selectItem, 4) + '\n'
						fout.write(s)
						s = 'typeMax: ' + self.tree.GetItemText(selectItem, 5) + '\n'
						fout.write(s)

					for l in range(1, totalcount) :
						child_item = self.tree.GetNextSibling(child_item)
						source_filename = self.tree.GetItemText(child_item, 9) 
						self.OnSAVE_DB_ITEM(fout, type, child_item, source_filename)

						if culltable_item != None and self.tree.GetItemText(child_item, 0) != "-Cull Table" :
							source_filename = self.tree.GetItemText(culltable_item, 9) 
							self.OnSAVE_DB_ITEM(fout, type, culltable_item, source_filename)

							if len(self.tree.GetItemText(selectItem, 1)) == 0 :
								s = 'typeData: Continuous\n'
								fout.write(s)
							else :
								s = 'typeData: ' + self.tree.GetItemText(selectItem, 1) + '\n'
								fout.write(s)
							s = 'typeDecimate: ' + self.tree.GetItemText(selectItem, 3) + '\n'
							fout.write(s)
							if self.tree.GetItemText(selectItem, 12) != "" :
								s = 'typeSmooth: ' + self.tree.GetItemText(selectItem, 12) + '\n'
								fout.write(s)
							s = 'typeMin: ' + self.tree.GetItemText(selectItem, 4) + '\n'
							fout.write(s)
							s = 'typeMax: ' + self.tree.GetItemText(selectItem, 5) + '\n'
							fout.write(s)
							culltable_item = None

			for k in range(1, total) :
				selectItem = self.tree.GetNextSibling(selectItem)
				type = self.tree.GetItemText(selectItem, 0)

				if type == "Saved Tables" :
					totalcount = self.tree.GetChildrenCount(selectItem, False)
					if totalcount > 0 :
						child = self.tree.GetFirstChild(selectItem)
						child_item = child[0]
						source_filename =  self.tree.GetItemText(child_item, 9)
						if source_filename == "" :
							source_filename = "-"
						if "AFFINE" == self.tree.GetItemText(child_item, 1) :
							s = '\naffinetable: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 2) + ': ' + source_filename + '\n'
							fout.write(s)
						elif "SPLICE" == self.tree.GetItemText(child_item, 1) :
							s = '\nsplicetable: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 2) + ': ' + source_filename + '\n'
							fout.write(s)
						elif "ELD" == self.tree.GetItemText(child_item, 1) :
							s = '\neldtable: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 2) + ': ' + source_filename + '\n'
							fout.write(s)
						elif "CULL" == self.tree.GetItemText(child_item, 1) :
							s = '\nuni_culltable: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 2) + ': ' + source_filename + '\n'
							fout.write(s)

						for l in range(1, totalcount) :
							child_item = self.tree.GetNextSibling(child_item)
							source_filename =  self.tree.GetItemText(child_item, 9)
							if source_filename == "" :
								source_filename = "-"
							if "AFFINE" == self.tree.GetItemText(child_item, 1) :
								s = '\naffinetable: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 2) + ': ' + source_filename + '\n'
								fout.write(s)
							elif "SPLICE" == self.tree.GetItemText(child_item, 1) :
								s = '\nsplicetable: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 2) + ': ' + source_filename + '\n'
								fout.write(s)
							elif "ELD" == self.tree.GetItemText(child_item, 1) :
								s = '\neldtable: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 2) + ': ' + source_filename +  '\n'
								fout.write(s)
							elif "CULL" == self.tree.GetItemText(child_item, 1) :
								s = '\nuni_culltable: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 2) + ': ' + source_filename + '\n'
								fout.write(s)
				elif type == "Downhole Log Data"  :
					totalcount = self.tree.GetChildrenCount(selectItem, False)
					if totalcount > 0 :
						child = self.tree.GetFirstChild(selectItem)
						child_item = child[0]
						s = '\nlog: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 9) + ': ' +  self.tree.GetItemText(child_item, 11) + ': ' + self.tree.GetItemText(child_item, 2) +  ': ' + self.tree.GetItemText(child_item, 1) + ': ' + self.tree.GetItemText(child_item, 4) + ': ' +  self.tree.GetItemText(child_item, 5) + ': ' + self.tree.GetItemText(child_item, 3) + ': ' + self.tree.GetItemText(child_item, 12) + '\n'
						fout.write(s)
						for l in range(1, totalcount) :
							child_item = self.tree.GetNextSibling(child_item)
							s = '\nlog: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 9) + ': ' +  self.tree.GetItemText(child_item, 11) + ': ' + self.tree.GetItemText(child_item, 2) +  ': ' + self.tree.GetItemText(child_item, 1) + ': ' + self.tree.GetItemText(child_item, 4) + ': ' +  self.tree.GetItemText(child_item, 5) + ': ' + self.tree.GetItemText(child_item, 3) + ': ' + self.tree.GetItemText(child_item, 12) + '\n'
							fout.write(s)
				elif type == "Stratigraphy" :
					totalcount = self.tree.GetChildrenCount(selectItem, False)
					if totalcount > 0 :
						child = self.tree.GetFirstChild(selectItem)
						child_item = child[0]
						s = '\nstrat: ' + self.tree.GetItemText(child_item, 0) + ': ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 11) + ': ' + self.tree.GetItemText(child_item, 2) + '\n'
						fout.write(s)
						for l in range(1, totalcount) :
							child_item = self.tree.GetNextSibling(child_item)
							s = '\nstrat: ' + self.tree.GetItemText(child_item, 0) + ': ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 11) + ': ' + self.tree.GetItemText(child_item, 2) + '\n'
							fout.write(s)
				elif type == "Age Models" :
					totalcount = self.tree.GetChildrenCount(selectItem, False)
					if totalcount > 0 :
						child = self.tree.GetFirstChild(selectItem)
						child_item = child[0]
						if "Value" == self.tree.GetItemText(child_item, 0) :
							s = '\nage: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 9) + ': ' + self.tree.GetItemText(child_item, 2) + '\n'
							fout.write(s)
						else :
							s = '\nseries: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 9) + ': ' + self.tree.GetItemText(child_item, 2) + '\n'
							fout.write(s)
						for l in range(1, totalcount) :
							child_item = self.tree.GetNextSibling(child_item)
							if "Value" == self.tree.GetItemText(child_item, 0) :
								s = '\nage: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 9) + ': ' + self.tree.GetItemText(child_item, 2) + '\n'
								fout.write(s)
							else :
								s = '\nseries: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 9) + ': ' + self.tree.GetItemText(child_item, 2) + '\n'
								fout.write(s)
				elif type == "Image Data" :
					totalcount = self.tree.GetChildrenCount(selectItem, False)
					if totalcount > 0 :
						child = self.tree.GetFirstChild(selectItem)
						child_item = child[0]
						s = '\nimage: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 9) + ': ' + self.tree.GetItemText(child_item, 2) + '\n'
						fout.write(s)
						for l in range(1, totalcount) :
							child_item = self.tree.GetNextSibling(child_item)
							s = '\nimage: ' + self.tree.GetItemText(child_item, 8) + ': ' + self.tree.GetItemText(child_item, 6) + ': ' + self.tree.GetItemText(child_item, 7) + ': ' + self.tree.GetItemText(child_item, 9) + ': ' + self.tree.GetItemText(child_item, 2) + '\n'
							fout.write(s)
				elif type == "Section Summary":
					secsumm_name = self.tree.GetItemText(selectItem, 1)
					if secsumm_name != "":
						fout.write('\nsecsumm: ' + secsumm_name + '\n')
				else :
					totalcount = self.tree.GetChildrenCount(selectItem, False)
					culltable_item = None
					if totalcount > 0 :
						child = self.tree.GetFirstChild(selectItem)
						child_item = child[0]

						if self.tree.GetItemText(child_item, 0) == "-Cull Table" :
							culltable_item = child_item
						else :
							self.OnSAVE_DB_ITEM(fout, type, child_item, "")

							# DUPLICATE AAA
							if len(self.tree.GetItemText(selectItem, 1)) == 0 :
								s = 'typeData: Continuous\n'
								fout.write(s)
							else :
								s = 'typeData: ' + self.tree.GetItemText(selectItem, 1) + '\n'
								fout.write(s)
							s = 'typeDecimate: ' + self.tree.GetItemText(selectItem, 3) + '\n'
							fout.write(s)
							if self.tree.GetItemText(selectItem, 12) != "" :
								s = 'typeSmooth: ' + self.tree.GetItemText(selectItem, 12) + '\n'
								fout.write(s)
							s = 'typeMin: ' + self.tree.GetItemText(selectItem, 4) + '\n'
							fout.write(s)
							s = 'typeMax: ' + self.tree.GetItemText(selectItem, 5) + '\n'
							fout.write(s)
							#END DUPLICATE AAA

						for l in range(1, totalcount) :
							child_item = self.tree.GetNextSibling(child_item)
							source_filename = self.tree.GetItemText(child_item, 9) 
							self.OnSAVE_DB_ITEM(fout, type, child_item, source_filename)

							if culltable_item != None and self.tree.GetItemText(child_item, 0) != "-Cull Table" :
								source_filename = self.tree.GetItemText(culltable_item, 9) 
								self.OnSAVE_DB_ITEM(fout, type, culltable_item, source_filename)

								# DUPLICATE AAA
								if len(self.tree.GetItemText(selectItem, 1)) == 0 :
									s = 'typeData: Continuous\n'
									fout.write(s)
								else :
									s = 'typeData: ' + self.tree.GetItemText(selectItem, 1) + '\n'
									fout.write(s)
								s = 'typeDecimate: ' + self.tree.GetItemText(selectItem, 3) + '\n'
								fout.write(s)
								if self.tree.GetItemText(selectItem, 12) != "" :
									s = 'typeSmooth: ' + self.tree.GetItemText(selectItem, 12) + '\n'
									fout.write(s)
								s = 'typeMin: ' + self.tree.GetItemText(selectItem, 4) + '\n'
								fout.write(s)
								s = 'typeMax: ' + self.tree.GetItemText(selectItem, 5) + '\n'
								fout.write(s)
								# END DUPLICATE AAA
								culltable_item = None

		fout.close()


	def OnLOAD_ITEM(self, selectItem):
		#if self.tree.GetItemText(selectItem, 0) == "-Cull Table" :
		#	return 1 

		parentItem = self.tree.GetItemParent(selectItem)

		if self.firstIdx == None :
			self.firstIdx = parentItem 

		self.parent.CurrentDir = self.parent.DBPath + "db/" + self.tree.GetItemText(selectItem, 10)

		decivalue = self.tree.GetItemText(parentItem, 3)
		self.parent.filterPanel.decimate.SetValue(str(decivalue))
		ndecivalue = 1
		if decivalue != '' :
			ndecivalue = int(decivalue)

		coretype = self.tree.GetItemText(parentItem, 0)
		self.parent.CurrentType = coretype
		type, annot = self.parent.TypeStrToInt(coretype)

		if self.parent.Window.timeseries_flag == False  :
			y_data = self.tree.GetItemText(selectItem, 13)
			idx = y_data.find("Age", 0)
			if idx >=0 :
				self.parent.Window.timeseries_flag = True

		self.parent.LOCK = 0
		filename = self.parent.DBPath + "db/" + self.tree.GetItemText(selectItem, 10) + self.tree.GetItemText(selectItem, 8) 

		ret = py_correlator.openHoleFile(filename, -1, type, ndecivalue, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, annot)
		if ret == 1 :
			s = filename + " (format : Correlator Internal " + "type : " + coretype + ")\n"
			self.parent.logFileptr.write(s)
			self.parent.LOCK = 1
		return ret


	def Find_UCULL(self, parentItem):
		child = self.FindItem(parentItem, 'Saved Tables')
		ret = [] 
		if child[0] == True :
			selectItem = child[1]
			totalcount = self.tree.GetChildrenCount(selectItem, False)
			if totalcount > 0 :
				child = self.tree.GetFirstChild(selectItem)
				child_item = child[0]
				type = self.tree.GetItemText(child_item, 1)
				flag = self.tree.GetItemText(child_item, 2)
				if type == "CULL" and flag == "Enable" :
					return child_item 
				for k in range(1, totalcount) :
					child_item = self.tree.GetNextSibling(child_item)
					type = self.tree.GetItemText(child_item, 1)
					flag = self.tree.GetItemText(child_item, 2)
					if type == "CULL" and flag == "Enable" :
						return child_item 
		return None


	def OnLOAD_TABLE(self, parentItem):
		child = self.FindItem(parentItem, 'Saved Tables')
		ret = [] 
		if child[0] == True :
			selectItem = child[1]
			totalcount = self.tree.GetChildrenCount(selectItem, False)
			affine_item = None
			splice_item = None
			eld_item = None
			if totalcount > 0 :
				child = self.tree.GetFirstChild(selectItem)
				child_item = child[0]
				type = self.tree.GetItemText(child_item, 1)
				flag = self.tree.GetItemText(child_item, 2)
				if type == "AFFINE" and flag == "Enable" :
					affine_item = child_item 
				elif type == "SPLICE" and flag == "Enable" :
					splice_item = child_item 
				elif type == "ELD" and flag == "Enable" :
					eld_item = child_item 

				for k in range(1, totalcount) :
					child_item = self.tree.GetNextSibling(child_item)
					type = self.tree.GetItemText(child_item, 1)
					flag = self.tree.GetItemText(child_item, 2)
					if affine_item == None and type == "AFFINE" and flag == "Enable" :
						affine_item = child_item 
					elif splice_item == None and type == "SPLICE" and flag == "Enable" :
						splice_item = child_item 
					elif eld_item == None and type == "ELD" and flag == "Enable" :
						eld_item = child_item 

			path = self.parent.DBPath + 'db/' + self.tree.GetItemText(parentItem, 0)  + '/'
			if affine_item != None :
				py_correlator.openAttributeFile(path +self.tree.GetItemText(affine_item, 8), 0)
				s = "Affine Table: " + path + self.tree.GetItemText(affine_item, 8) + "\n"
				self.parent.logFileptr.write(s)
				ret.append(True)
			else :
				ret.append(False)

			if splice_item != None :
				#if affine_item == None :
				#	self.parent.OnShowMessage("Error", "Splice table needs affine table enable", 1)
				#	return False
				ret_splice = py_correlator.openSpliceFile(path +self.tree.GetItemText(splice_item, 8))
				if ret_splice == "error" : 
					self.parent.OnShowMessage("Error", "Could not Make Splice Records", 1)

				s = "Splice Table: " + path + self.tree.GetItemText(splice_item, 8) + "\n"
				self.parent.logFileptr.write(s)

				#self.parent.splicedOpened = 1
				ret.append(True)
			else :
				ret.append(False)

			if eld_item != None :
				py_correlator.openAttributeFile(path +self.tree.GetItemText(eld_item, 8), 1)
				s = "ELD Table: " + path + self.tree.GetItemText(eld_item, 8) + "\n"
				self.parent.logFileptr.write(s)

				if self.parent.Window.LogData != [] :
					self.parent.eldPanel.SetFlag(True)
					mudline = py_correlator.getMudline()
					if mudline != 0.0 :
						self.parent.OnUpdateLogData(True)
					#if splice_item != None and affine_item != None :
					retdata = py_correlator.getData(13)
					if retdata != "" :
						self.parent.ParseSaganData(retdata)
						self.parent.autoPanel.OnButtonEnable(0, False)
					retdata = "" 
				ret.append(True)
			else :
				ret.append(False)

		return ret 


	# return TreeItemID of first enabled Downhole Log Data item (if any), else None
	def GetEnabledLog(self, parentItem):
		enabledLogItem = None
		dldItem = self.FindItem(parentItem, 'Downhole Log Data')
		if dldItem[0] == True:
			logCount = self.tree.GetChildrenCount(dldItem[1], False)
			(child, cookie) = self.tree.GetFirstChild(dldItem[1])
			while child.IsOk():
				if self.tree.GetItemText(child, 2) == "Enable":
					enabledLogItem = child
					break
				(child, cookie) = self.tree.GetNextChild(dldItem[1], cookie)
		return enabledLogItem
	
	def OnLOAD_LOG(self, parentItem):
		child_item = self.GetEnabledLog(parentItem)
		if child_item is not None:
			path = self.parent.CurrentDir + self.tree.GetItemText(child_item, 8) 
			py_correlator.openLogFile(path, int(self.tree.GetItemText(child_item, 11)))

			s = "Downhole Log Data: " + path + self.tree.GetItemText(child_item, 8) + "\n"
			self.parent.logFileptr.write(s)

			decivalue = self.tree.GetItemText(child_item, 3)
			if decivalue > 1 :
				py_correlator.decimate('Log', int(decivalue))
				
			smooth = -1
			smooth_data = self.tree.GetItemText(child_item, 12)
			if smooth_data != "" :
				smooth_array = smooth_data.split()
				if "UnsmoothedOnly" == smooth_array[2] :
					smooth = 0
				elif "SmoothedOnly" == smooth_array[2] :
					smooth = 1
				elif "Smoothed&Unsmoothed" == smooth_array[2] :
					smooth = 2 
				if smooth_array[1] == "Depth(cm)" :
					py_correlator.smooth('Log', int(smooth_array[0]), 2)
				else :
					py_correlator.smooth('Log', int(smooth_array[0]), 1)
			print "Getting log data...",
			ret = py_correlator.getData(5)
			print "done"
			if ret != "" :
				mudline = py_correlator.getMudline()
				if mudline != 0.0 :
					self.parent.Window.isLogShifted = True

				self.parent.filterPanel.OnLock()
				self.parent.ParseData(ret, self.parent.Window.LogData)
				min = float(self.tree.GetItemText(child_item, 4))
				max = float(self.tree.GetItemText(child_item, 5))
				coef = max - min
				newrange = []
				newrange = 'log', min, max, coef, smooth, True
				self.parent.Window.range.append(newrange)
				self.parent.UpdateSMOOTH_LogData()

				self.parent.filterPanel.OnRelease()
				self.parent.Window.isLogMode = 1
				self.parent.Window.SpliceTieData = []
				self.parent.Window.CurrentSpliceCore = -1
				self.parent.autoPanel.OnButtonEnable(0, True)
				return True
		return False


	def OnLOAD_SERIES(self, parentItem):
		child = self.FindItem(parentItem, 'Age Models')
		if child[0] == True :
			selectItem = child[1]
			totalcount = self.tree.GetChildrenCount(selectItem, False)
			if totalcount > 0 :
				child = self.tree.GetFirstChild(selectItem)
				child_item = child[0]
				if self.tree.GetItemText(child_item, 0) == "Model" and self.tree.GetItemText(child_item, 2) == "Enable" :
					path = self.parent.CurrentDir + self.tree.GetItemText(child_item, 8)
					self.OnLOAD_SERIESFILE(path)
				else :
					for k in range(1, totalcount) :
						child_item = self.tree.GetNextSibling(child_item)
						if self.tree.GetItemText(child_item, 0) == "Model" and self.tree.GetItemText(child_item, 2) == "Enable" :
							path = self.parent.CurrentDir + self.tree.GetItemText(child_item, 8)
							self.OnLOAD_SERIESFILE(path)
							break


	def OnLOAD_SERIESFILE(self, filename):
		agesFile = open(filename, "r")
		count = len(self.parent.Window.UserdefStratData) + 1
		idx = 0
		while True :
			#name = "X" + str(count)
			line = agesFile.readline()
			if len(line) == 0 :
				break
			if line[0] != "#" :
				# Leg, Site, Mbsf, Mcd, Eld, Age, Sediment Rate, Age Datum, Comment, Type
				tokens = line.split()
				if tokens[0] == 'null' :
					conitnue
				depth = float(tokens[2])
				mcd = float(tokens[3])
				eld = float(tokens[4])
				age = float(tokens[5])

				name = ""
				type = ""
				if idx == 0 :
					name = "X" 
					type = "handpick" 
				else :
					ret = self.parent.Window.GetAGENAME(depth, age)
					if ret == None :
						continue
					name = ret[0]
					type = ret[1]

				strItem = ""
				bm0 = int(100.00 * float(depth)) / 100.00;
				str_ba = str(bm0)
				max_ba = len(str_ba)
				start_ba = str_ba.find('.', 0)
				str_ba = str_ba[start_ba:max_ba]
				max_ba = len(str_ba)
				if platform_name[0] != "Windows" :
					if max_ba < 3 :
						strItem = str(bm0) + "0 \t"
					else :
						strItem = str(bm0) + "\t"

					bm0 = int(100.00 * float(mcd)) / 100.00;
					str_ba = str(bm0)
					max_ba = len(str_ba)
					start_ba = str_ba.find('.', 0)
					str_ba = str_ba[start_ba:max_ba]
					max_ba = len(str_ba)
					if max_ba < 3 :
						strItem = strItem + str(bm0) + "0 \t" + str(bm0) + "0 \t"
					else :
						strItem = strItem + str(bm0) + "\t" + str(bm0) + "\t"

					str_ba = str(age)
					max_ba = len(str_ba)
					start_ba = str_ba.find('.', 0)
					str_ba = str_ba[start_ba:max_ba]
					max_ba = len(str_ba)
					if max_ba < 3 :
						strItem += str(age) + "0 \t" + name
					else :
						strItem += str(age) + "\t" + name
					if type == "handpick" :
						strItem += " *handpick"
				else :
					if max_ba < 3 :
						strItem = str(bm0) + "0 \t"
					else :
						strItem = str(bm0) + " \t"

					bm0 = int(100.00 * float(mcd)) / 100.00;
					str_ba = str(bm0)
					max_ba = len(str_ba)
					start_ba = str_ba.find('.', 0)
					str_ba = str_ba[start_ba:max_ba]
					max_ba = len(str_ba)
					if max_ba < 3 :
						strItem = strItem + str(bm0) + "0 \t" + str(bm0) + "0 \t"
					else :
						strItem = strItem + str(bm0) + " \t" + str(bm0) + " \t"

					str_ba = str(age)
					max_ba = len(str_ba)
					start_ba = str_ba.find('.', 0)
					str_ba = str_ba[start_ba:max_ba]
					max_ba = len(str_ba)
					if max_ba < 3 :
						strItem += str(age) + "0 \t" + name
					else :
						strItem += str(age) + " \t" + name
					if type == "handpick" :
						strItem += " *handpick"                                       
				if idx == 0 :
					self.parent.Window.firstPntAge = age
					self.parent.Window.firstPntDepth = depth 
					self.parent.agePanel.ageList.Delete(0)
					self.parent.agePanel.ageList.InsertItems([strItem], 0)
					idx = 1
					continue

				order = self.parent.agePanel.OnAddAgeToList(strItem)
				self.parent.Window.AddToAgeList(name, depth, mcd, age, order, type)

				if self.parent.Window.maxAgeRange < age :
					self.parent.Window.maxAgeRange = int(age) + 2
					self.parent.agePanel.max_age.SetValue(str(self.parent.Window.maxAgeRange))

				count = count + 1
		agesFile.close()

		s = "Age Series: " + filename + "\n"
		self.parent.logFileptr.write(s)


	def OnLOAD_AGE(self, parentItem):
		child = self.FindItem(parentItem, 'Age Models')
		if child[0] == True :
			selectItem = child[1]
			totalcount = self.tree.GetChildrenCount(selectItem, False)
			if totalcount > 0 :
				child = self.tree.GetFirstChild(selectItem)
				child_item = child[0]
				if self.tree.GetItemText(child_item, 0) == "Value" and self.tree.GetItemText(child_item, 2) == "Enable" :
					path = self.parent.CurrentDir + self.tree.GetItemText(child_item, 8)
					self.OnLOAD_AGEFILE(path)
				else :
					for k in range(1, totalcount) :
						child_item = self.tree.GetNextSibling(child_item)
						if self.tree.GetItemText(child_item, 0) == "Value" and self.tree.GetItemText(child_item, 2) == "Enable" :
							path = self.parent.CurrentDir + self.tree.GetItemText(child_item, 8)
							self.OnLOAD_AGEFILE(path)
							break


	def OnLOAD_AGEFILE(self, filename):
		agesFile = open(filename, "r")

		for line in agesFile :
			if len(line) == 0 :
				continue	
			if line[0] != "#" :
				tokens = line.split()
				if len(tokens) == 1 :
					tokens = line.split(",")
				max = len(tokens)
				if max > 0 : 
					temp_line = tokens[0]
					last = temp_line.find(",", 0)
					if last >= 0 :
						out_i = 0
						while out_i < max :
							temp_line = tokens[out_i]
							out_i += 1
							temp_line = temp_line.split(",")
							in_max = len(temp_line)
							i = 0
							while i < in_max :
								depth = float(temp_line[i])
								i += 1
								rate = py_correlator.getMcdRate(depth)
								mcd = depth * rate
								mcd = int(100.0 * float(mcd)) / 100.0;
								age = float(temp_line[i])
								i += 1
								name = temp_line[i]
								i += 1
								comment = temp_line[i]
								i += 1

								ret = self.parent.Window.CHECK_AGE(name, depth, age)
								if ret == False :
									self.parent.Window.AddUserdefAge(name, depth, mcd, age, comment)
								if self.parent.Window.maxAgeRange < age :
									self.parent.Window.maxAgeRange = int(age) + 2
									self.parent.agePanel.max_age.SetValue(str(self.parent.Window.maxAgeRange))
						continue
						
				i = 0
				while i < max :
					depth = float(tokens[i])
					i += 1
					rate = py_correlator.getMcdRate(depth)
					mcd = depth * rate
					mcd = int(100.0 * float(mcd)) / 100.0;
					age = float(tokens[i])
					i += 1
					name = tokens[i]
					i += 1
					comment = tokens[i]
					i += 1

					ret = self.parent.Window.CHECK_AGE(name, depth, age)
					if ret == False :
						self.parent.Window.AddUserdefAge(name, depth, mcd, age, comment)

					if self.parent.Window.maxAgeRange < age :
						self.parent.Window.maxAgeRange = int(age) + 2
						self.parent.agePanel.max_age.SetValue(str(self.parent.Window.maxAgeRange))
		agesFile.close()

		s = "Age Model: " + filename + "\n"
		self.parent.logFileptr.write(s)


	def OnLOAD_STRAT(self, parentItem):
		child = self.FindItem(parentItem, 'Stratigraphy')
		if child[0] == True :
			selectItem = child[1]
			totalcount = self.tree.GetChildrenCount(selectItem, False)
			if totalcount > 0 :
				child = self.tree.GetFirstChild(selectItem)
				child_item = child[0]
				if self.tree.GetItemText(child_item, 2) == "Enable" :
					path = self.parent.CurrentDir + self.tree.GetItemText(child_item, 8)
					success = py_correlator.openStratFile(path, self.tree.GetItemText(child_item, 0))
					if success == 1 :
						s = "Stratigraphy: " + path + self.tree.GetItemText(child_item, 0) + "\n"
						self.parent.logFileptr.write(s)
						self.parent.UpdateStratData()
						self.parent.agePanel.OnAddStratToList()
				for k in range(1, totalcount) :
					child_item = self.tree.GetNextSibling(child_item)
					if self.tree.GetItemText(child_item, 2) == "Enable" :
						path = self.parent.CurrentDir + self.tree.GetItemText(child_item, 8)
						success = py_correlator.openStratFile(path, self.tree.GetItemText(child_item, 0))
						if success == 1 :
							s = "Stratigraphy: " + path + self.tree.GetItemText(child_item, 0) + "\n"
							self.parent.logFileptr.write(s)
							self.parent.UpdateStratData()
							self.parent.agePanel.OnAddStratToList()


	def OnLOAD_UCULLTABLE(self, selectItem, type):
		if selectItem ==  None :
			return

		filename = self.parent.DBPath + 'db/' + self.tree.GetItemText(selectItem, 10)
		filename += self.tree.GetItemText(selectItem, 8)

		if filename != "" :
			coretype, annot = self.parent.TypeStrToInt(type)

			py_correlator.openCullTable(filename, coretype, annot)
			s = "Cull Table: " + filename + " For type-" + type + "\n"
			self.parent.logFileptr.write(s)

			if coretype == 4 :
				type = "Natural Gamma"

			f = open(filename, 'r+')
			l = []
			l.append(type)
			l.append(True)
			for line in f :
				modifiedLine = line[0:-1].split()
				if modifiedLine[0] == 'null' :
					continue
				max = len(modifiedLine)
				if modifiedLine[1] == 'Top' :
					value = modifiedLine[2]
					l.append(value)
				elif modifiedLine[1] == 'Range' :
					if max >= 4 : 
						value = modifiedLine[2]
						l.append(value)
						value = modifiedLine[3]
						l.append(value)
					if max == 6 : 
						#l.append(True)
						value = modifiedLine[4]
						l.append(value)
						value = modifiedLine[5]
						l.append(value)
				elif modifiedLine[1] == 'Core' :
					value = modifiedLine[2]
					l.append(value)
				elif modifiedLine[1] == 'Type' :
					break
			f.close()
			#print "[DEBUG] UPDATE CULL INFO : " + str(l)
			icount =0
			if type == "Natural Gamma" :
				type = "NaturalGamma"

			for r in self.cullData :
				if r[0] == type :
					self.cullData.pop(icount)
					self.cullData.insert(icount, l)
					break
				icount += 1


	def OnLOAD_CULLTABLE(self, selectItem, type):
		totalcount = self.tree.GetChildrenCount(selectItem, False)
		if totalcount > 0 :
			child = self.tree.GetFirstChild(selectItem)
			child_item = child[0]
			filename = ""

			if self.tree.GetItemText(child_item, 0) == "-Cull Table" and self.tree.GetItemText(child_item, 2) == "Enable" :
				filename = self.parent.CurrentDir + self.tree.GetItemText(child_item, 8)
			else :
				for k in range(1, totalcount) :
					child_item = self.tree.GetNextSibling(child_item)
					if self.tree.GetItemText(child_item, 0) == "-Cull Table" and self.tree.GetItemText(child_item, 2) == "Enable" :
						filename = self.parent.CurrentDir + self.tree.GetItemText(child_item, 8)
						break

			if filename != "" :
				coretype, annot = self.parent.TypeStrToInt(type)

				py_correlator.openCullTable(filename, coretype, annot)
				s = "Cull Table: " + filename + " For type-" + type + "\n"
				self.parent.logFileptr.write(s)

				if coretype == 4 :
					type = "Natural Gamma"

				f = open(filename, 'r+')
				l = []
				l.append(type)
				l.append(True)
				for line in f :
					modifiedLine = line[0:-1].split()
					if modifiedLine[0] == 'null' :
						continue
					max = len(modifiedLine)
					if modifiedLine[1] == 'Top' :
						value = modifiedLine[2]
						l.append(value)
					elif modifiedLine[1] == 'Range' :
						if max >= 4 : 
							value = modifiedLine[2]
							l.append(value)
							value = modifiedLine[3]
							l.append(value)
						if max == 6 : 
							#l.append(True)
							value = modifiedLine[4]
							l.append(value)
							value = modifiedLine[5]
							l.append(value)
					elif modifiedLine[1] == 'Core' :
						value = modifiedLine[2]
						l.append(value)
					elif modifiedLine[1] == 'Type' :
						break
				f.close()
				#print "[DEBUG] UPDATE CULL INFO : " + str(l)
				self.cullData.append(l) 
			else :
				l = []
				l.append(type)
				l.append(False)
				self.cullData.append(l) 

			return filename


	def UpdateRANGE(self, type, item):
		totalcount = self.tree.GetChildrenCount(item, False)
		selectItem = None
		if totalcount > 0 :
			child = self.tree.GetFirstChild(item)
			child_item = child[0]
			if self.tree.GetItemText(child_item, 0) == type :
				selectItem = child_item 
			else :
				for k in range(1, totalcount) :
					child_item = self.tree.GetNextSibling(child_item)
					if self.tree.GetItemText(child_item, 0) == type :
						selectItem = child_item 
						break

		if selectItem != None :
			totalcount = self.tree.GetChildrenCount(selectItem, False)
			if totalcount > 0 :
				child = self.tree.GetFirstChild(selectItem)
				child_item = child[0]
				min = float(self.tree.GetItemText(child_item, 4))
				max = float(self.tree.GetItemText(child_item, 5))
				for k in range(1, totalcount) :
					child_item = self.tree.GetNextSibling(child_item)
					float_min = float(self.tree.GetItemText(child_item, 4))
					float_max = float(self.tree.GetItemText(child_item, 5))
					if float_min < min :
						min = float_min
					if float_max > max :
						max = float_max

				self.tree.SetItemText(selectItem, str(min), 4)
				self.tree.SetItemText(selectItem, str(max), 5)

				self.OnUPDATE_DB_FILE(self.tree.GetItemText(item, 0), item)


	def Update_PROPERTY_ITEM(self, items):
		self.propertyIdx = None
		parentItem = None
		for item in items :
			if len(self.tree.GetItemText(item, 8)) > 0 :
				parentItem = self.tree.GetItemParent(item)
				parentItem = self.tree.GetItemParent(parentItem)
				break
			else :
				type = self.tree.GetItemText(item, 0)
				if type.find("-", 0) == -1 :
					parentItem = self.tree.GetItemParent(item)
				else :
					parentItem = item
				break

		if parentItem != None :
			child = self.FindItem(parentItem, 'Saved Tables')
			if child[0] == True :
				self.propertyIdx = child[1]

		if self.propertyIdx == None :
			self.parent.OnShowMessage("Error", "Could not find Property", 1)


	def UpdateMINMAX(self, type, min, max):
		self.Update_PROPERTY_ITEM(self.selectBackup)

		if type != 'Log' :
			if self.propertyIdx != None :
				parentItem = self.tree.GetItemParent(self.propertyIdx)
				child = self.FindItem(parentItem, type)
				if child[0] == True :
					selectItem = child[1]
					self.tree.SetItemText(selectItem, str(min), 4)
					self.tree.SetItemText(selectItem, str(max), 5)
					self.parent.Window.UpdateRANGE(type, min, max)
					# UPDATE RANGE
					self.OnUPDATE_DB_FILE(self.tree.GetItemText(parentItem, 0), parentItem)
					self.parent.Window.UpdateDrawing()
		else :
			# Log
			if self.propertyIdx != None :
				parentItem = self.tree.GetItemParent(self.propertyIdx)
				child = self.FindItem(parentItem, "Downhole Log Data")
				if child[0] == True :
					selectItem = child[1]
					totalcount = self.tree.GetChildrenCount(selectItem, False)
					if totalcount > 0 :
						child = self.tree.GetFirstChild(selectItem)
						child_item = child[0]
						if self.tree.GetItemText(child_item, 2) == "Enable" :
							self.tree.SetItemText(child_item, str(min), 4)
							self.tree.SetItemText(child_item, str(max), 5)
							self.OnUPDATE_DB_FILE(self.tree.GetItemText(parentItem, 0), parentItem)
						else :
							for k in range(1, totalcount) :
								child_item = self.tree.GetNextSibling(child_item)
								if self.tree.GetItemText(child_item, 2) == "Enable" :
									self.tree.SetItemText(child_item, str(min), 4)
									self.tree.SetItemText(child_item, str(max), 5)
									self.OnUPDATE_DB_FILE(self.tree.GetItemText(parentItem, 0), parentItem)
									break
				self.parent.Window.UpdateDrawing()


	def OnLOAD(self):
		self.propertyIdx = None
		self.title = ""
		self.cullData = []
		self.firstIdx = None 

		self.parent.INIT_CHANGES()

		items = self.tree.GetSelections()
		self.selectBackup = self.tree.GetSelections()

		if len(items) > 0 :
			self.parent.OnNewData(None)
		else :
			self.parent.OnShowMessage("Error", "Please, select data", 1)
			return False

		if self.parent.Window.HoleData != [] :
			self.logFileptr.write("Closed All Files Loaded. \n\n")


		# NEED TO FIND UNIVERSAL CULL
		universal_cull_item = None 

		self.parent.Window.range = [] 
		self.parent.Window.AltSpliceData = []
		self.parent.Window.selectedType = ""
		self.parent.TimeChange = False
		self.parent.Window.timeseries_flag = False 
		parentItem = None
		previousType = "" 
		previousItem = None 
		count_load = 0
		for selectItem in items :
			if self.tree.GetItemText(selectItem, 0) == "Root" :
				self.parent.OnShowMessage("Error", "Root is not allowed to select", 1)
				return False
			elif self.tree.GetItemText(selectItem, 0) == "Saved Tables" :
				self.parent.OnShowMessage("Error", "Table is not allowed to select", 1)
				return False
			else :
				# if there is no subItem, then this function returns "" back
				#self.parent.CurrentDataNo = selectrows[0]

				self.parent.logFileptr.write("Load Files: \n")

				# hole node
				if len(self.tree.GetItemText(selectItem, 8)) > 0 :
					parentItem = self.tree.GetItemParent(selectItem)
					type = self.tree.GetItemText(parentItem, 0)
					if universal_cull_item == None :
						cull_parentItem = self.tree.GetItemParent(parentItem)
						universal_cull_item = self.Find_UCULL(cull_parentItem) 

					# it appears that a cull table will never be loaded for a single hole
					# since multiple selection is impossible thus previousType will == "" when
					# we reach this point. Strangely, that's for the best since loading a cull
					# table before loading data results in a C++ side crash (because dataptr is NULL).
					if previousType != "" and previousType != type and count_load > 0 :
						ret = self.OnLOAD_CULLTABLE(parentItem, type)
						if ret == "" :
							self.OnLOAD_UCULLTABLE(universal_cull_item, type)

						smooth = -1
						smooth_data = self.tree.GetItemText(previousItem, 12)
						if smooth_data != "" :
							smooth_array = smooth_data.split()
							if "UnsmoothedOnly" == smooth_array[2] :
								smooth = 0 
							elif "SmoothedOnly" == smooth_array[2] :
								smooth = 1 
							elif "Smoothed&Unsmoothed" == smooth_array[2] :
								smooth = 2 
							if smooth_array[1] == "Depth(cm)" :
								py_correlator.smooth(type, int(smooth_array[0]), 2)
							else :
								py_correlator.smooth(type, int(smooth_array[0]), 1)

						continue_flag = True 
						if self.tree.GetItemText(previousItem, 1) == "Discrete" :
							continue_flag = False 

						min = float(self.tree.GetItemText(previousItem, 4))
						max = float(self.tree.GetItemText(previousItem, 5))
						coef = max - min
						newrange = previousType, min, max, coef, smooth, continue_flag
						self.parent.Window.range.append(newrange)

					if self.tree.GetItemText(selectItem, 2) == "Enable" and self.tree.GetItemText(selectItem, 0) != "-Cull Table" :
						if self.OnLOAD_ITEM(selectItem) == 0 :
							self.parent.OnNewData(None)
							self.parent.OnShowMessage("Error", "Can not Load File", 1)
							return
						else :
							count_load += 1 
							previousType = type 
							previousItem = selectItem

				else : # not hole node, other types?
					type = self.tree.GetItemText(selectItem, 0)
					if type.find("-", 0) == -1 : # if non-site node, appears to be holeset
						parentItem = self.tree.GetItemParent(selectItem)
						if universal_cull_item == None :
							universal_cull_item = self.Find_UCULL(parentItem) 

						totalcount = self.tree.GetChildrenCount(selectItem, False)
						if totalcount > 0 :
							child = self.tree.GetFirstChild(selectItem)
							child_item = child[0]
							if self.tree.GetItemText(child_item, 2) == "Enable" and self.tree.GetItemText(child_item, 0) != "-Cull Table" :
								if self.OnLOAD_ITEM(child_item) == 0 :
									self.parent.OnNewData(None)
									self.parent.OnShowMessage("Error", "Can not Load File", 1)
									return
								else :
									count_load += 1 
							for k in range(1, totalcount) :
								child_item = self.tree.GetNextSibling(child_item)
								if self.tree.GetItemText(child_item, 2) == "Enable" and self.tree.GetItemText(child_item, 0) != "-Cull Table" :
									if self.OnLOAD_ITEM(child_item) == 0 :
										self.parent.OnNewData(None)
										self.parent.OnShowMessage("Error", "Can not Load File", 1)
										return
									else :
										count_load += 1 
										
							if count_load > 0 :
								ret = self.OnLOAD_CULLTABLE(selectItem, type)
								if ret == "" :
									self.OnLOAD_UCULLTABLE(universal_cull_item, type)

								smooth = -1
								smooth_data = self.tree.GetItemText(selectItem, 12)
								if smooth_data != "" :
									smooth_array = smooth_data.split()
									if "UnsmoothedOnly" == smooth_array[2] :
										smooth = 0 
									elif "SmoothedOnly" == smooth_array[2] :
										smooth = 1 
									elif "Smoothed&Unsmoothed" == smooth_array[2] :
										smooth = 2 
									if smooth_array[1] == "Depth(cm)" :
										py_correlator.smooth(type, int(smooth_array[0]), 2)
									else :
										py_correlator.smooth(type, int(smooth_array[0]), 1)

								continue_flag = True 
								if self.tree.GetItemText(selectItem, 1) == "Discrete" :
									continue_flag = False 

								min = float(self.tree.GetItemText(selectItem, 4))
								max = float(self.tree.GetItemText(selectItem, 5))
								coef = max - min
								newrange = type, min, max, coef, smooth, continue_flag
								self.parent.Window.range.append(newrange) 

					else : # must be a site node
						parentItem = selectItem
						if universal_cull_item == None :
							universal_cull_item = self.Find_UCULL(parentItem) 

						total = self.tree.GetChildrenCount(parentItem, False)
						if total > 0 :
							child = self.tree.GetFirstChild(parentItem)
							selectItem = child[0]
							str_txt = self.tree.GetItemText(selectItem, 0)

							if str_txt not in STD_SITE_NODES:
								totalcount = self.tree.GetChildrenCount(selectItem, False)
								if totalcount > 0 :
									child = self.tree.GetFirstChild(selectItem)
									child_item = child[0]
									if self.tree.GetItemText(child_item, 2) == "Enable" and self.tree.GetItemText(child_item, 0) != "-Cull Table":
										if self.OnLOAD_ITEM(child_item) == 0 :
											self.parent.OnNewData(None)
											self.parent.OnShowMessage("Error", "Can not Load File", 1)
											return
										else :
											count_load += 1
									for k in range(1, totalcount) :
										child_item = self.tree.GetNextSibling(child_item)
										if self.tree.GetItemText(child_item, 2) == "Enable"  and self.tree.GetItemText(child_item, 0) != "-Cull Table":
											if self.OnLOAD_ITEM(child_item) == 0  :
												self.parent.OnNewData(None)
												self.parent.OnShowMessage("Error", "Can not Load File", 1)
												return
											else :
												count_load += 1

								if count_load > 0 :
									ret = self.OnLOAD_CULLTABLE(selectItem, str_txt)
									if ret == "" :
										self.OnLOAD_UCULLTABLE(universal_cull_item, str_txt)

									smooth = -1
									smooth_data = self.tree.GetItemText(selectItem, 12)
									if smooth_data != "" :
										smooth_array = smooth_data.split()
										if "UnsmoothedOnly" == smooth_array[2] :
											smooth = 0 
										elif "SmoothedOnly" == smooth_array[2] :
											smooth = 1 
										elif "Smoothed&Unsmoothed" == smooth_array[2] :
											smooth = 2 
										if smooth_array[1] == "Depth(cm)" :
											py_correlator.smooth(str_txt, int(smooth_array[0]), 2)
										else :
											py_correlator.smooth(str_txt, int(smooth_array[0]), 1)

									continue_flag = True 
									if self.tree.GetItemText(selectItem, 1) == "Discrete" :
										continue_flag = False 

									min = float(self.tree.GetItemText(selectItem, 4))
									max = float(self.tree.GetItemText(selectItem, 5))
									coef = max - min
									newrange = str_txt, min, max, coef, smooth, continue_flag
									self.parent.Window.range.append(newrange)

							for k in range(1, total) :
								selectItem = self.tree.GetNextSibling(selectItem)
								str_txt = self.tree.GetItemText(selectItem, 0)
								if str_txt not in STD_SITE_NODES: 
									totalcount = self.tree.GetChildrenCount(selectItem, False)
									if totalcount > 0 :
										child = self.tree.GetFirstChild(selectItem)
										child_item = child[0]
										if self.tree.GetItemText(child_item, 2) == "Enable"  and self.tree.GetItemText(child_item, 0) != "-Cull Table":
											if self.OnLOAD_ITEM(child_item) == 0 :
												self.parent.OnNewData(None)
												self.parent.OnShowMessage("Error", "Can not Load File", 1)
												return
											else :
												count_load += 1
										for l in range(1, totalcount) :
											child_item = self.tree.GetNextSibling(child_item)
											if self.tree.GetItemText(child_item, 2) == "Enable"  and self.tree.GetItemText(child_item, 0) != "-Cull Table" :
												if self.OnLOAD_ITEM(child_item) == 0 :
													self.parent.OnNewData(None)
													self.parent.OnShowMessage("Error", "Can not Load File", 1)
													return
												else :
													count_load += 1

									if count_load > 0 :
										ret = self.OnLOAD_CULLTABLE(selectItem, str_txt)
										if ret == "" :
											self.OnLOAD_UCULLTABLE(universal_cull_item, str_txt)

										smooth = -1
										smooth_data = self.tree.GetItemText(selectItem, 12)
										if smooth_data != "" :
											smooth_array = smooth_data.split()
											if "UnsmoothedOnly" == smooth_array[2] :
												smooth = 0 
											elif "SmoothedOnly" == smooth_array[2] :
												smooth = 1 
											elif "Smoothed&Unsmoothed" == smooth_array[2] :
												smooth = 2 
											if smooth_array[1] == "Depth(cm)" :
												py_correlator.smooth(str_txt, int(smooth_array[0]), 2)
											else :
												py_correlator.smooth(str_txt, int(smooth_array[0]), 1)

										continue_flag = True 
										if self.tree.GetItemText(selectItem, 1) == "Discrete" :
											continue_flag = False 
										min = float(self.tree.GetItemText(selectItem, 4))
										max = float(self.tree.GetItemText(selectItem, 5))
										coef = max - min
										newrange = str_txt, min, max, coef, smooth, continue_flag
										self.parent.Window.range.append(newrange)


		if count_load == 0 :
			self.parent.OnShowMessage("Error", "There is no data loaded", 1)
			self.parent.OnNewData(None)
			return
			
		if previousType != "" :
			titleItem = self.tree.GetItemParent(parentItem)
			ret = self.OnLOAD_CULLTABLE(parentItem, previousType)
			if ret == "" :
				self.OnLOAD_UCULLTABLE(universal_cull_item, type)

			smooth = -1
			smooth_data = self.tree.GetItemText(parentItem, 12)
			if smooth_data != "" :
				smooth_array = smooth_data.split()
				if "UnsmoothedOnly" == smooth_array[2] :
					smooth = 0 
				elif "SmoothedOnly" == smooth_array[2] :
					smooth = 1 
				elif "Smoothed&Unsmoothed" == smooth_array[2] :
					smooth = 2 
				if smooth_array[1] == "Depth(cm)" :
					py_correlator.smooth(previousType, int(smooth_array[0]), 2)
				else :
					py_correlator.smooth(previousType, int(smooth_array[0]), 1)

			continue_flag = True 
			if self.tree.GetItemText(parentItem, 1) == "Discrete" :
				continue_flag = False 
			min = float(self.tree.GetItemText(parentItem, 4))
			max = float(self.tree.GetItemText(parentItem, 5))
			coef = max - min
			newrange = type, min, max, coef, smooth, continue_flag
			self.parent.Window.range.append(newrange)
			parentItem = titleItem

		self.parent.OnUpdateDepthStep()
		tableLoaded = [] 
		logLoaded = False
		if parentItem != None :
			logLoaded = self.OnLOAD_LOG(parentItem)
			self.parent.OnInitDataUpdate()
			tableLoaded = self.OnLOAD_TABLE(parentItem)
			self.parent.Window.LogselectedTie = -1 
			self.parent.Window.activeSATie = -1 
			total = self.tree.GetChildrenCount(parentItem, False)
			self.title = self.tree.GetItemText(parentItem, 0)
			if total > 0 :
				child = self.tree.GetFirstChild(parentItem)
				child_item = child[0]
				str_txt = self.tree.GetItemText(child_item, 0)
				if str_txt == "Saved Tables" : 
					self.propertyIdx = child_item 
				else :
					for l in range(1, total) :
						child_item = self.tree.GetNextSibling(child_item)
						str_txt = self.tree.GetItemText(child_item, 0)
						if str_txt == "Saved Tables" : 
							self.propertyIdx = child_item
							break

			self.OnLOAD_STRAT(parentItem)
			self.OnLOAD_AGE(parentItem)
			self.OnLOAD_SERIES(parentItem)

		self.parent.logFileptr.write("\n")
		self.parent.LOCK = 0 

		if tableLoaded != [] :
			if tableLoaded[1] == True :
				self.parent.OnInitDataUpdate()
				self.parent.InitSPLICE()
				self.parent.UpdateSPLICE(False)
				#self.parent.UpdateSMOOTH_SPLICE(False)
				if len(self.parent.Window.SpliceCore) > 0:
					self.parent.splicePanel.OnButtonEnable(4, True) # enable Append button
				self.parent.autoPanel.SetCoreList(1, [])
				self.parent.filterPanel.OnRegisterHole("Spliced Records")
				r = self.parent.Window.range[0]
				firsttype = self.tree.GetItemText(self.firstIdx, 0)
				for subr in self.parent.Window.range :
					if subr[0] == firsttype :
						r = subr
				self.parent.Window.selectedType = r[0]
				newrange = "splice", r[1], r[2], r[3], 0, r[5]
				self.parent.Window.range.append(newrange)
			else :
				self.parent.UpdateCORE()
				self.parent.UpdateSMOOTH_CORE()
				self.parent.autoPanel.SetCoreList(0, self.parent.Window.HoleData)

			if tableLoaded[2] == True :
				self.parent.UpdateELD(True)
		else :
			self.parent.UpdateCORE()
			self.parent.UpdateSMOOTH_CORE()
			self.parent.autoPanel.SetCoreList(0, self.parent.Window.HoleData)

		self.parent.Window.ShowLog = False 
		if logLoaded == True :
			self.parent.Window.ShowLog = True
			self.parent.filterPanel.OnRegisterHole("Log")

		self.parent.OnDisableMenu(1, True)
		self.parent.LOCK = 1

		if self.parent.showReportPanel == 1 :
			self.parent.OnUpdateReport()

		self.parent.ShowDisplay()

		# LOAD SECTION
		self.parent.NewDATA_SEND()
		self.parent.Window.UpdateScroll(1)
		self.parent.Window.UpdateScroll(2)

		self.parent.Window.SetFocusFromKbd()
		self.parent.Window.UpdateDrawing()

		self.parent.compositePanel.OnUpdatePlots() # make sure growth rate is updated

		self.parent.compositePanel.saveButton.Enable(True)
		if self.parent.Window.LogData  == [] :
			self.parent.splicePanel.saveButton.Enable(True)
			self.parent.splicePanel.altButton.Enable(True)
			self.parent.splicePanel.newButton.Enable(True)
		else :
			self.parent.eldPanel.saveButton.Enable(True)
			self.parent.autoPanel.saveButton.Enable(True)
			self.parent.splicePanel.altButton.Enable(False)
			self.parent.splicePanel.newButton.Enable(False)

		return True
		

	def Add_TABLE(self, title, sub_title, updateflag, importflag, source_filename):
		if importflag == False and len(self.selectBackup) == 0 :
			self.parent.OnShowMessage("Error", "Could not find selected items", 1)
			return

		items = [] 
		if importflag == False :
			items = self.selectBackup
		else :
			items = self.tree.GetSelections()

		self.Update_PROPERTY_ITEM(items)
		property = self.propertyIdx
			
		#property = self.propertyIdx
		#if property == None :
		#	property = self.tree.GetSelection()
		#	parentItem = self.tree.GetItemParent(property)
		#	self.title = self.tree.GetItemText(parentItem, 0)
		#	self.parent.CurrentDir = self.parent.DBPath + 'db/' + self.title + '/'

		title_flag = False
		totalcount = self.tree.GetChildrenCount(property, False)
		if totalcount > 0 :
			child = self.tree.GetFirstChild(property)
			child_item = child[0]
			if self.tree.GetItemText(child_item, 1) == title and self.tree.GetItemText(child_item, 2) == "Enable" :
				title_flag = True
			else :
				for k in range(1, totalcount) :
					child_item = self.tree.GetNextSibling(child_item)
					if self.tree.GetItemText(child_item, 1) == title and self.tree.GetItemText(child_item, 2) == "Enable" :
						title_flag = True
						break
		if title_flag == False :
			updateflag = False
			#print "[DEBUG] No " + title + " Table is Enable" 

		ith = 0
		max_ith = 0
		temp_filename = ""
		if updateflag == False :
			totalcount = self.tree.GetChildrenCount(property, False)
			if totalcount > 0 :
				child = self.tree.GetFirstChild(property)
				child_item = child[0]
				if self.tree.GetItemText(child_item, 1) == title :
					temp_filename = self.tree.GetItemText(child_item, 8) 
					last = temp_filename.find(".", 0) 
					start = last + 1
					last = temp_filename.find(".", start)
					ith = int(temp_filename[start:last])
					if max_ith < ith  :
						max_ith = ith
				for k in range(1, totalcount) :
					child_item = self.tree.GetNextSibling(child_item)
					if self.tree.GetItemText(child_item, 1) == title :
						temp_filename = self.tree.GetItemText(child_item, 8) 
						last = temp_filename.find(".", 0) 
						start = last + 1
						last = temp_filename.find(".", start)
						ith = int(temp_filename[start:last])
						if max_ith < ith  :
							max_ith = ith
		ith = max_ith + 1
		#print "[DEBUG] file index number is " + str(ith)

		filename = ''
		child = self.FindItemProperty(property, title)
		if child[0] == False or updateflag == False :
			subroot = self.tree.AppendItem(property, "Table" )
			self.tree.SetItemText(subroot, title, 1)

			self.tree.Expand(subroot)

			filename = self.title + '.' + str(ith) + '.' + sub_title + '.table'
			self.tree.SetItemText(subroot,  filename, 8)

			self.tree.SetItemText(subroot, "Enable", 2)
			self.tree.SetItemTextColour(subroot, wx.BLUE)

			tempstamp = str(datetime.today())
			last = tempstamp.find(":", 0)
			last = tempstamp.find(":", last+1)
			#stamp = tempstamp[0:10] + "," + tempstamp[12:16]
			stamp = tempstamp[0:last] 

			self.tree.SetItemText(subroot, stamp, 6)

			self.tree.SetItemText(subroot, self.parent.user, 7)
			if len(source_filename) > 0 :
				self.tree.SetItemText(subroot, source_filename, 9)

			self.tree.SetItemText(subroot, self.title + '/', 10)

			dblist_f = open(self.parent.DBPath + 'db/' + self.title + '/datalist.db', 'a+')
			s = '\n' + sub_title + 'table: ' + filename + ': ' + stamp + ': ' + self.parent.user + ': Enable' + ': ' + source_filename +'\n'
                        dblist_f.write(s)
			dblist_f.close()
		else :
			subroot = child[1]

			tempstamp = str(datetime.today())
			last = tempstamp.find(":", 0)
			last = tempstamp.find(":", last+1)
			#stamp = tempstamp[0:10] + "," + tempstamp[12:16]
			stamp = tempstamp[0:last]

			self.tree.SetItemText(subroot, stamp, 6)
			self.tree.SetItemText(subroot, self.parent.user, 7)

			parentItem = self.tree.GetItemParent(property)
			filename = self.tree.GetItemText(subroot, 8) 
			self.OnUPDATE_DB_FILE(self.title, parentItem)

                fullname = ''
                if sys.platform == 'win32' :
                        fullname = self.parent.DBPath + 'db\\' + self.title + '\\' + filename
                else :
                        fullname = self.parent.DBPath + 'db/' + self.title + '/' + filename
		return fullname


	def OnUPDATE_SMOOTH(self, smType, method, value, opt, mode):
		s = ""
		if method != "None" :
			s = str(value) + " " + str(opt) + " " + str(mode)

		#if self.currentIdx == [] : 
		if self.selectBackup == [] :
			return

		if smType == 'Log' :
			self.Update_PROPERTY_ITEM(self.selectBackup)

			if self.propertyIdx != None :
				parentItem = self.tree.GetItemParent(self.propertyIdx)
				child = self.FindItem(parentItem, "Downhole Log Data")
				if child[0] == True :
					selectItem = child[1]
					totalcount = self.tree.GetChildrenCount(selectItem, False)
					if totalcount > 0 :
						child = self.tree.GetFirstChild(selectItem)
						child_item = child[0]
						if self.tree.GetItemText(child_item, 2) == "Enable" :
							self.tree.SetItemText(child_item, s, 12)
							self.OnUPDATE_DB_FILE(self.tree.GetItemText(parentItem, 0), parentItem)
						else :
							for k in range(1, totalcount) :
								child_item = self.tree.GetNextSibling(child_item)
								if self.tree.GetItemText(child_item, 2) == "Enable" :
									self.tree.SetItemText(child_item, s, 12)
									self.OnUPDATE_DB_FILE(self.tree.GetItemText(parentItem, 0), parentItem)
									break
			return 


		parentItem = None
		#for selectItem in self.currentIdx :
		for selectItem in self.selectBackup :
			if len(self.tree.GetItemText(selectItem, 8)) > 0 :
				if self.tree.GetItemText(selectItem, 0) == '-Cull Table' :
					continue

				parentItem = self.tree.GetItemParent(selectItem)
				type = self.tree.GetItemText(parentItem, 0)

				if smType == "All Holes" or smType == type :
					self.tree.SetItemText(parentItem, s, 12)
					smooth = -1
					if "UnsmoothedOnly" == mode :
						smooth = 0 
					elif "SmoothedOnly" == mode :
						smooth = 1 
					elif "Smoothed&Unsmoothed" == mode :
						smooth = 2 
					if method == "None" :
						smooth = -1
					self.parent.Window.UpdateSMOOTH(type, smooth)
				parentItem = self.tree.GetItemParent(parentItem)
			else :
				type = self.tree.GetItemText(selectItem, 0)
				if type.find("-", 0) == -1 :
					if smType == "All Holes" or smType == type :
						self.tree.SetItemText(selectItem, s, 12)
						smooth = -1
						if "UnsmoothedOnly" == mode :
							smooth = 0 
						elif "SmoothedOnly" == mode :
							smooth = 1 
						elif "Smoothed&Unsmoothed" == mode :
							smooth = 2 
						if method == "None" :
							smooth = -1
						self.parent.Window.UpdateSMOOTH(type, smooth)
					parentItem = self.tree.GetItemParent(selectItem)
				else :
					# TITLE-LEG-SITE
					parentItem = selectItem
					total = self.tree.GetChildrenCount(parentItem, False)
					if total > 0 :
						child = self.tree.GetFirstChild(parentItem)
						selectItem = child[0]
						type = self.tree.GetItemText(selectItem, 0)
						if smType == "All Holes" or smType == type :
							self.tree.SetItemText(selectItem, s, 12)
							smooth = -1
							if "UnsmoothedOnly" == mode :
								smooth = 0 
							elif "SmoothedOnly" == mode :
								smooth = 1 
							elif "Smoothed&Unsmoothed" == mode :
								smooth = 2 
							if method == "None" :
								smooth = -1
							self.parent.Window.UpdateSMOOTH(type, smooth)
						for k in range(1, total) :
							selectItem = self.tree.GetNextSibling(selectItem)
							type = self.tree.GetItemText(selectItem, 0)
							if smType == "All Holes" or smType == type :
								self.tree.SetItemText(selectItem, s, 12)
								smooth = -1
								if "UnsmoothedOnly" == mode :
									smooth = 0 
								elif "SmoothedOnly" == mode :
									smooth = 1 
								elif "Smoothed&Unsmoothed" == mode :
									smooth = 2 
								if method == "None" :
									smooth = -1
								self.parent.Window.UpdateSMOOTH(type, smooth)

		if parentItem != None :
			self.OnUPDATE_DB_FILE(self.tree.GetItemText(parentItem, 0), parentItem)


	def OnUPDATE_CULLTABLE(self, cullType):
		#if self.currentIdx == [] :
		if self.selectBackup == [] :
			return

		min = 999.99
		max = -999.99
		title = ""
		type = ""
		parentItem = None 
		selectItem = None
		#for selectItem in self.currentIdx :
		for selectItem in self.selectBackup :
			if len(self.tree.GetItemText(selectItem, 8)) > 0 :
				parentItem = self.tree.GetItemParent(selectItem)
				type = self.tree.GetItemText(parentItem, 0)
				if cullType == "All Holes" or cullType == type :
					ret = py_correlator.getRange(type)
					if ret != None :
						min = int(100.0 * float(ret[0])) / 100.0
						max = int(100.0 * float(ret[1])) / 100.0
					self.tree.SetItemText(parentItem, str(min), 4)
					self.tree.SetItemText(parentItem, str(max), 5)
					self.parent.Window.UpdateRANGE(type, min, max)

				parentItem = self.tree.GetItemParent(parentItem)
				title = self.tree.GetItemText(parentItem, 0)
			else :
				type = self.tree.GetItemText(selectItem, 0)
				if type.find("-", 0) == -1 :
					if cullType == "All Holes" or cullType == type :
						ret = py_correlator.getRange(type)
						if ret != None :
							min = int(100.0 * float(ret[0])) / 100.0
							max = int(100.0 * float(ret[1])) / 100.0
						self.tree.SetItemText(selectItem, str(min), 4)
						self.tree.SetItemText(selectItem, str(max), 5)
						self.parent.Window.UpdateRANGE(type, min, max)

					parentItem = self.tree.GetItemParent(selectItem)
					title = self.tree.GetItemText(parentItem, 0)
				else :
					# TITLE-LEG-SITE
					parentItem = selectItem
					title = self.tree.GetItemText(parentItem, 0)

					total = self.tree.GetChildrenCount(parentItem, False)
					if total > 0 :
						child = self.tree.GetFirstChild(parentItem)
						child_item = child[0]
						type = self.tree.GetItemText(child_item , 0)
						if type not in STD_SITE_NODES:
							if cullType == "All Holes" or cullType == type :
								ret = py_correlator.getRange(type)
								if ret != None :
									min = int(100.0 * float(ret[0])) / 100.0
									max = int(100.0 * float(ret[1])) / 100.0
								selectItem = child_item 
								self.tree.SetItemText(selectItem, str(min), 4)
								self.tree.SetItemText(selectItem, str(max), 5)
								self.parent.Window.UpdateRANGE(type, min, max)
						for k in range(1, total) :
							child_item = self.tree.GetNextSibling(child_item)
							type = self.tree.GetItemText(child_item, 0)
							if type not in STD_SITE_NODES:
								if cullType == "All Holes" or cullType == type :
									ret = py_correlator.getRange(type)
									if ret != None :
										min = int(100.0 * float(ret[0])) / 100.0
										max = int(100.0 * float(ret[1])) / 100.0
									selectItem = child_item 
									self.tree.SetItemText(selectItem, str(min), 4)
									self.tree.SetItemText(selectItem, str(max), 5)
									self.parent.Window.UpdateRANGE(type, min, max)

		if parentItem != None :
			type = self.tree.GetItemText(selectItem, 0)
			source_path = self.tree.GetItemText(selectItem, 9)
			filename = self.Add_CULLTABLE(selectItem, type, False, source_path)
			self.OnUPDATE_DB_FILE(title, parentItem)
			py_correlator.saveCullTable(filename, type)

			s = "Save Cull Table: " + filename + " For type-" + type + "\n"
			self.parent.logFileptr.write(s)


	def Set_NAMING(self, type, title, filetype):
			datatype = type 
			if type == "NaturalGamma" :
				datatype = "ngfix"
			elif type == "Susceptibility" :
				datatype = "susfix"
			elif type == "Reflectance" :
				datatype = "reflfix"
			elif type == "Bulk Density(GRA)" :
				datatype = "grfix" 
			elif type == "Pwave" :
				datatype = "pwfix" 
			elif type == "Other" :
				datatype = "otherfix" 

			filename = title + '.' + datatype + '.' + filetype + '.table' 
			return filename


	def Add_CULLTABLE(self, item, type, isUniversal, source_path):
		parentItem = self.tree.GetItemParent(item)
		child = self.FindItem(item, '-Cull Table')
		filename = ''
		title = ''
		if child[0] == False :
			# HYEJUNG
			subroot = None
			if isUniversal == True :
				subroot = self.tree.AppendItem(item, 'Table' )
				self.tree.SetItemText(subroot, "CULL", 1)
			else :
				subroot = self.tree.AppendItem(item, '-Cull Table' )
			self.tree.Expand(subroot)

			self.tree.SetItemText(subroot, type + '.' +  self.parent.user + '.cull.table', 8)

			self.tree.SetItemTextColour(subroot, wx.BLUE)
			self.tree.SetItemText(subroot, "Enable", 2)

			tempstamp = str(datetime.today())
			last = tempstamp.find(":", 0)
			last = tempstamp.find(":", last+1)
			#stamp = tempstamp[0:10] + "," + tempstamp[12:16]
			stamp = tempstamp[0:last]
			self.tree.SetItemText(subroot, stamp, 6)
			self.tree.SetItemText(subroot, self.parent.user, 7)

			title = self.tree.GetItemText(parentItem, 0)

			filename = self.Set_NAMING(type, title, 'cull')
			self.tree.SetItemText(subroot, filename, 8)
			self.tree.SetItemText(subroot, source_path, 9)

			self.tree.SetItemText(subroot, title + '/', 10)

			#dblist_f = open(self.parent.DBPath +'db/' + title + '/datalist.db', 'a+')
			#s = '\nculltable: ' + filename + ': ' + stamp + ': ' + self.parent.user + ': ' + self.tree.GetItemText(subroot, 2) + '\n'
			#dblist_f.write(s)
			#dblist_f.close()

			if isUniversal == True :
				dblist_f = open(self.parent.DBPath +'db/' + title + '/datalist.db', 'a+')
				s = '\nuni_culltable: ' + filename + ': ' + stamp + ': ' + self.parent.user + ': ' + self.tree.GetItemText(subroot, 2) + ': ' + source_path + '\n'
				dblist_f.write(s)
				dblist_f.close()
			else :
				self.OnUPDATE_DB_FILE(title, parentItem)
		else :
			selectItem = child[1]
			tempstamp = str(datetime.today())
			last = tempstamp.find(":", 0)
			last = tempstamp.find(":", last+1)
			#stamp = tempstamp[0:10] + "," + tempstamp[12:16]
			stamp = tempstamp[0:last]
			self.tree.SetItemText(selectItem, stamp, 6)
			self.tree.SetItemText(selectItem, self.parent.user, 7)

			title = self.tree.GetItemText(parentItem, 0)
			#self.OnUPDATE_DB_FILE(title, parentItem)
			filename = self.tree.GetItemText(selectItem, 8)
			# why does not update db file here ????

		fullname = self.parent.DBPath + 'db/' + title + '/' + filename
		return fullname


	def GetCULL(self, type):
		for data in self.cullData :
			if str(data[0]) == type :
				return data 
		return None


	def UpdateCULL(self, type, bcull, cullValue, cullNumber, value1, value2, sign1, sign2, join):
		if type == 'Log' :
			print "[DEBUG] Log cull"
		else :
			size = len(type)
			type = type[4:size]

		if type == "Natural Gamma" :
			type = "NaturalGamma"

		for data in self.cullData :
			if str(data[0]) == type :
				self.cullData.remove(data)
				break
		if bcull == 0 : # remove existing cull ("No Cull" radio checked)
			l = []
			l.append(type)
			l.append(False)
			self.cullData.append(l)
		else : # cull parameters
			l = []
			l.append(type)
			l.append(True)
			l.append(str(cullValue))

			if sign1 == 1 :
				l.append('>')
			else :
				l.append('<')
			l.append(str(value1))

			if join == 2 :
				if sign2 == 1 :
					l.append('>')
				else :
					l.append('<')
				l.append(str(value2))

			if cullNumber >= 0 :
				l.append(str(cullNumber))
			self.cullData.append(l)

	def GetDECIMATE(self, type):
		self.Update_PROPERTY_ITEM(self.selectBackup)

		if self.propertyIdx != None : 
			parentItem = self.tree.GetItemParent(self.propertyIdx)
			total = self.tree.GetChildrenCount(parentItem, False)
			if total > 0 :
				child = self.tree.GetFirstChild(parentItem)
				selectItem = child[0]
				str_txt = self.tree.GetItemText(selectItem, 0)
				if str_txt == type :
					return self.tree.GetItemText(selectItem, 3), self.tree.GetItemText(selectItem, 12)
				for k in range(1, total) :
					selectItem = self.tree.GetNextSibling(selectItem)
					str_txt = self.tree.GetItemText(selectItem, 0)
					if str_txt == type :
						return self.tree.GetItemText(selectItem, 3), self.tree.GetItemText(selectItem, 12)
		return None


	def OnUPDATEDECIMATE(self, deciType, deciValue):
		#if self.currentIdx == [] :
		if self.selectBackup == [] :
			return

		if deciType == 'Log' :
			self.Update_PROPERTY_ITEM(self.selectBackup)
			if self.propertyIdx != None :
				parentItem = self.tree.GetItemParent(self.propertyIdx)
				child = self.FindItem(parentItem, "Downhole Log Data")
				if child[0] == True :
					selectItem = child[1]
					totalcount = self.tree.GetChildrenCount(selectItem, False)
					if totalcount > 0 :
						child = self.tree.GetFirstChild(selectItem)
						child_item = child[0]
						if self.tree.GetItemText(child_item, 2) == "Enable" :
							self.tree.SetItemText(child_item, str(deciValue), 3)
							self.OnUPDATE_DB_FILE(self.tree.GetItemText(parentItem, 0), parentItem)
						else :
							for k in range(1, totalcount) :
								child_item = self.tree.GetNextSibling(child_item)
								if self.tree.GetItemText(child_item, 2) == "Enable" :
									self.tree.SetItemText(child_item, str(deciValue), 3)
									self.OnUPDATE_DB_FILE(self.tree.GetItemText(parentItem, 0), parentItem)
									break
			return 

		titleItems = None
		#for selectItem in self.currentIdx :
		for selectItem in self.selectBackup :
			if len(self.tree.GetItemText(selectItem, 8)) > 0 :
				parentItem = self.tree.GetItemParent(selectItem)
				if self.tree.GetItemText(selectItem, 0) == '-Cull Table':
					continue

				type = "All " + self.tree.GetItemText(selectItem, 0)
				if deciType == "All Holes" or deciType == type :
					self.tree.SetItemText(selectItem, str(deciValue), 3)
					self.tree.SetItemText(parentItem, str(deciValue), 3)

					parentItem = self.tree.GetItemParent(parentItem)
					title = self.tree.GetItemText(parentItem, 0)
					self.OnUPDATE_DB_FILE(title, parentItem)
			else :
				type = self.tree.GetItemText(selectItem, 0)
				if type.find("-", 0) == -1 :
					parentItem = self.tree.GetItemParent(selectItem)
					type = "All " + type
					if deciType == "All Holes" or deciType == type :
						self.tree.SetItemText(selectItem, str(deciValue), 3)
						totalcount = self.tree.GetChildrenCount(selectItem, False)
						if totalcount > 0 :
							child = self.tree.GetFirstChild(selectItem)
							child_item = child[0]
							if self.tree.GetItemText(child_item, 0) != '-Cull Table':
								self.tree.SetItemText(child_item, str(deciValue), 3)
								for k in range(1, totalcount) :
									child_item = self.tree.GetNextSibling(child_item)
									if self.tree.GetItemText(child_item, 0) != '-Cull Table':
										self.tree.SetItemText(child_item, str(deciValue), 3)

						title = self.tree.GetItemText(parentItem, 0)
						self.OnUPDATE_DB_FILE(title, parentItem)
				else :
					# TITLE-LEG-SITE
					parentItem = selectItem
					total = self.tree.GetChildrenCount(parentItem, False)
					if total > 0 :
						child = self.tree.GetFirstChild(parentItem)
						selectItem = child[0]
						# HYEJUNG
						str_txt = self.tree.GetItemText(selectItem, 0)
						if str_txt not in STD_SITE_NODES:
							type = "All " + str_txt
							if deciType == "All Holes" or deciType == type :
								self.tree.SetItemText(selectItem, str(deciValue), 3)
								totalcount = self.tree.GetChildrenCount(selectItem, False)
								if totalcount > 0 :
									child = self.tree.GetFirstChild(selectItem)
									child_item = child[0]
									if self.tree.GetItemText(child_item, 0) != '-Cull Table':
										self.tree.SetItemText(child_item, str(deciValue), 3)
										for k in range(1, totalcount) :
											child_item = self.tree.GetNextSibling(child_item)
											if self.tree.GetItemText(child_item, 0) != '-Cull Table':
												self.tree.SetItemText(child_item, str(deciValue), 3)

						for k in range(1, total) :
							selectItem = self.tree.GetNextSibling(selectItem)
							str_txt = self.tree.GetItemText(selectItem, 0)
							if str_txt not in STD_SITE_NODES:
								type = "All " + str_txt
								if deciType == "All Holes" or deciType == type :
									self.tree.SetItemText(selectItem, str(deciValue), 3)
									totalcount = self.tree.GetChildrenCount(selectItem, False)
									if totalcount > 0 :
										child = self.tree.GetFirstChild(selectItem)
										child_item = child[0]
										if self.tree.GetItemText(child_item, 0) != '-Cull Table':
											self.tree.SetItemText(child_item, str(deciValue), 3)
											for l in range(1, totalcount) :
												child_item = self.tree.GetNextSibling(child_item)
												if self.tree.GetItemText(child_item, 0) != '-Cull Table':
													self.tree.SetItemText(child_item, str(deciValue), 3)

						title = self.tree.GetItemText(parentItem, 0)
						self.OnUPDATE_DB_FILE(title, parentItem)


	# brgtodo never used
# 	def OnUPDATEMINMAX(self, min, max, type):
# 		#selectrows = self.listPanel.GetSelectedRows()
# 		strdatatype = ""
# 		if type == "All Natural Gamma" :
# 			strdatatype = "NaturalGamma"	
# 		elif type == "All Susceptibility" :
# 			strdatatype = "Susceptibility"
# 		elif type == "All Reflectance" :
# 			strdatatype = "Reflectance"
# 		elif type == "All Bulk Density(GRA)" : 
# 			strdatatype = "Bulk Density(GRA)"
# 		elif type == "All Pwave" : 
# 			strdatatype = "Pwave"
# 		elif type == "All Other" : 
# 			strdatatype = "Other"
#			
		#if strdatatype != "" :
		#	for row in selectrows :
		#		if self.listPanel.GetCellValue(row, 10) == strdatatype:
		#			self.listPanel.SetCellValue(row, 18, str(min))
		#			self.listPanel.SetCellValue(row, 19, str(max))
		#			break
		#elif type == "All Holes" :
		#	for row in selectrows :
		#		self.listPanel.SetCellValue(row, 18, str(min))
		#		self.listPanel.SetCellValue(row, 19, str(max))


	""" Confirm existence of dirs and files corresponding to sites listed in root-level
	datalist.db. If not, regenerate root datalist.db to reflect filesystem state. """
	def ValidateDatabase(self):
		if os.access(self.parent.DBPath + 'db/', os.F_OK) == False :
			os.mkdir(self.parent.DBPath + 'db/')

		if os.access(self.parent.DBPath + 'db/datalist.db', os.F_OK) == False :
			root_f = open(self.parent.DBPath + 'db/datalist.db', 'w+')
			root_f.close()

		validate = True 
		root_f = open(self.parent.DBPath + 'db/datalist.db', 'r+')
		for root_line in root_f :
			list = root_line.splitlines()
			if list[0] == '' :
				continue
			for data_item in list :
				if os.access(self.parent.DBPath + 'db/' + data_item + '/datalist.db', os.F_OK) == False :
					validate = False 
					break

		root_f.close()
		if validate == False :
			print "[ERROR] Data list is not valide, DATALIST WILL BE RE-GENERATED"
			root_f = open(self.parent.DBPath + 'db/datalist.db', 'w+')
			list = os.listdir(self.parent.DBPath + 'db/')
			for dir in list :
				if dir != "datalist.db" :
					if dir.find("-", 0) > 0 :
						if os.access(self.parent.DBPath + 'db/' + dir + '/datalist.db', os.F_OK) == True :
							root_f.write(dir + "\n")
			root_f.close()

	def LoadSessionReports(self):
		log_report = self.tree.AppendItem(self.root, 'Session Reports')
		list = os.listdir(self.parent.DBPath + 'log/')
		for dir in list :
			if dir != ".DS_Store" :
				report_item = self.tree.AppendItem(log_report, 'Report')
				self.tree.SetItemText(report_item, dir, 1)
				last = dir.find(".", 0)
				user = dir[0:last]
				self.tree.SetItemText(report_item, user, 7)
				start = last + 1
				last = dir.find("-", start)
				last = dir.find("-", last+1)
				last = dir.find("-", last+1)
				time = dir[start:last] + " "
				start = last + 1
				last = dir.find("-", start)
				time += dir[start:last] + ":"
				start = last + 1
				last = dir.find(".", start)
				time += dir[start:last]
				self.tree.SetItemText(report_item, time, 6)
		if len(list) >= 50 :
			self.parent.OnShowMessage("Information", "Please, Clean Session Reports", 1)

	def LoadDatabase(self):
		self.ValidateDatabase()
		self.LoadSessionReports()
		siteNames = self.LoadSiteNames()
		self.loadedSites = self.LoadSites(siteNames) # return instead?

	def LoadSiteNames(self):
		dbRootFile = open(self.parent.DBPath + 'db/datalist.db', 'r+')
		loadedSites = []
		for site in dbRootFile:
			site = site.strip()
			if site == '' or site in loadedSites:
				continue
			else:
				loadedSites.append(site)
		return loadedSites

	# parse single-line types
	def ParseOthers(self, site, siteLines):
		for line in siteLines:
			tokens = line.split(': ')
			if tokens[0] == 'affinetable':
				affine = AffineData()
				affine.FromTokens(tokens)
				site.affineTables.append(affine)
			elif tokens[0] == 'splicetable':
				splice = SpliceData()
				splice.FromTokens(tokens)
				site.spliceTables.append(splice)
			elif tokens[0] == 'eldtable':
				eld = EldData()
				eld.FromTokens(tokens)
				site.eldTables.append(eld)
			elif tokens[0] == 'log':
				log = DownholeLogTable()
				log.FromTokens(tokens)
				site.logTables.append(log)
			elif tokens[0] == 'strat':
				strat = StratTable()
				strat.FromTokens(tokens)
				site.stratTables.append(strat)
			elif tokens[0] == 'age':
				age = AgeTable()
				age.FromTokens(tokens)
				site.ageTables.append(age)
			elif tokens[0] == 'series':
				series = SeriesTable()
				series.FromTokens(tokens)
				site.seriesTables.append(series)
			elif tokens[0] == 'image':
				image = ImageTable()
				image.FromTokens(tokens)
				site.imageTables.append(image)

	def ParseHoleSets(self, site, siteLines):
		curType = None
		for line in siteLines:
			tokens = line.split(': ')
			#if tokens[0] == 'type' and tokens[1] not in site.holeSets:
			#	curType = tokens[1]
			#	site.holeSets[tokens[1]] = HoleSet(curType)
			if tokens[0] == 'type':
				curType = tokens[1]
				site.AddHoleSet(curType)
			elif tokens[0] == 'typeData':
				site.holeSets[curType].continuous = ParseContinuousToken(tokens[1])
			elif tokens[0] == 'typeDecimate':
				site.holeSets[curType].decimate = ParseDecimateToken(tokens[1])
			elif tokens[0] == 'typeSmooth':
				site.holeSets[curType].smooth = tokens[1]
			elif tokens[0] == 'typeMin':
				site.holeSets[curType].min = tokens[1]
			elif tokens[0] == 'typeMax':
				site.holeSets[curType].max = tokens[1]
			elif tokens[0] == 'culltable' or tokens[0] == 'uni_culltable':
				cull = CullTable()
				cull.FromTokens(tokens)
				site.holeSets[curType].cullTable = cull

	# For some reason holes are the only data we serialize as multiple lines. Why?
	# Maintaining as single lines (like everything else) would simplify parsing.
	def ParseHoles(self, site, siteLines):
		curHole = None
		curType = None
		for line in siteLines:
			token = line.split(': ')
			if token[0] == 'hole':
				if curHole != None:
					site.AddHole(curType, curHole)
				curHole = HoleData(token[1])
			elif token[0] == 'type':
				curType = token[1]
 			elif token[0] == "dataName":
				curHole.dataName = token[1]
 			elif token[0] == "depth" :
				curHole.depth = token[1]
 			elif token[0] == "file" :
				curHole.file = token[1]
 			elif token[0] == "min" :
				curHole.min = token[1]
 			elif token[0] == "max" :
				curHole.max = token[1]
 			elif token[0] == "updatedTime" :
				curHole.updatedTime = token[1]
 			elif token[0] == "enable" :
				curHole.enable = ParseEnableToken(token[1])
 			elif token[0] == "byWhom" :
				curHole.byWhom = token[1]
 			elif token[0] == "source" :
				curHole.origSource = token[1]
 			elif token[0] == "data" :
				curHole.data = token[1]
		if curHole != None:
			site.AddHole(curType, curHole)

	def LoadSites(self, siteNames):
		loadedSites = []
		for siteName in siteNames:
			site = SiteData(siteName)

			siteFile = open(self.parent.DBPath + 'db/' + siteName + '/datalist.db', 'r+')
			siteLines = siteFile.readlines()
			for idx, line in enumerate(siteLines):
				siteLines[idx] = siteLines[idx].strip('\r\n')

			self.ParseHoleSets(site, siteLines)
			self.ParseHoles(site, siteLines)
			self.ParseOthers(site, siteLines)
			site.dump()
			loadedSites.append(site)

		return loadedSites

	# brg 12/4/2013: Builds data manager UI
	def OnLOADCONFIG(self):
		#self.LoadDatabase() # 9/12/2014 brg: for new db manager, don't bother loading for now

		# self.parent - "master" Correlator class
		# self - old dbmanager (has required variables and methods)
		# self.dbPanel - Notebook panel in which to embed DBView
		# self.loadedSites - list of sites loaded from root datalist.db
		#self.dbview = DBView(self.parent, self, self.dbPanel, self.loadedSites)

		self.ValidateDatabase()

		root_f = open(self.parent.DBPath + 'db/datalist.db', 'r+')
		hole = "" 
		loaded_item_list = []
		for root_line in root_f :
			list = root_line.splitlines()
			if list[0] == '' :
				continue

			for data_item in list :
				found = False
				for loaded_item in loaded_item_list :
					if loaded_item == data_item :
						found = True 
						break
				if found == True :
					break
				loaded_item_list.append(data_item)

				sub_f = open(self.parent.DBPath + 'db/' + data_item + '/datalist.db', 'r+')

				curSite = SiteData(data_item)

				root = self.tree.AppendItem(self.root, data_item) # site name
				self.tree.SetItemBold(root, True)
				property_child = self.tree.AppendItem(root, 'Saved Tables')
				log_child = self.tree.AppendItem(root, 'Downhole Log Data')
				strat_child = self.tree.AppendItem(root, 'Stratigraphy')
				age_child = self.tree.AppendItem(root, 'Age Models')
				image_child = self.tree.AppendItem(root, 'Image Data')
				secsumm_child = self.tree.AppendItem(root, 'Section Summary')
				self.tree.SortChildren(root)
				child = None
				hole_child = None
				cmd = None
				token_nums = 0

				for sub_line in sub_f :
					# 12/4/2013 brg: Pretty sure this is unnecessary as each sub_line
					# should already be a single line of sub_f without extra linebreaks,
					# i.e. this just makes a singleton list containing sub_line
					lines = sub_line.splitlines()

					for line in lines :
						token = line.split(': ')
						token_nums = len(token) 
						if token[0] == "hole" : # start a new hole
							hole = token[1]
							child = None
							hole_child = None
						elif token[0] == "type" :
							ret = self.FindItem(root, token[1])
							if ret[0] == False :
								child = self.tree.AppendItem(root, token[1])
								self.tree.SortChildren(root)
							else :
								child = ret[1]
							hole_child = self.tree.AppendItem(child, hole)
							self.tree.SortChildren(child)
							self.tree.SetItemText(hole_child, data_item+'/', 10)
						elif token[0] == "dataName" :
							if hole_child != None :
								self.tree.SetItemText(hole_child, token[1], 1)
								if token[1] == "?" :
									self.tree.SetItemText(hole_child, "Undefined", 1)
						elif token[0] == "depth" :
							if hole_child != None :
								self.tree.SetItemText(hole_child, token[1], 13)
						elif token[0] == "file" :
							if hole_child != None :
								self.tree.SetItemText(hole_child, token[1], 8)
						elif token[0] == "decimate" :
							if hole_child != None :
								self.tree.SetItemText(hole_child, token[1], 3)
						elif token[0] == "min" :
							if hole_child != None :
								self.tree.SetItemText(hole_child, token[1], 4)
						elif token[0] == "max" :
							if hole_child != None :
								self.tree.SetItemText(hole_child, token[1], 5)
						elif token[0] == "updatedTime" :
							if hole_child != None :
								self.tree.SetItemText(hole_child, token[1], 6)
						elif token[0] == "enable" :
							if hole_child != None :
								self.tree.SetItemText(hole_child, token[1], 2)
						elif token[0] == "byWhom" :
							if hole_child != None :
								self.tree.SetItemText(hole_child, token[1], 7)
						elif token[0] == "typeDecimate" :
							if child != None :
								self.tree.SetItemText(child, token[1], 3)
						elif token[0] == "typeData" :
							if child != None :
								self.tree.SetItemText(child, token[1], 1)
						elif token[0] == "typeMin" :
							if child != None :
								self.tree.SetItemText(child, token[1], 4)
						elif token[0] == "typeMax" :
							if child != None :
								self.tree.SetItemText(child, token[1], 5)
						elif token[0] == "typeSmooth" :
							if child != None :
								temp_max = len(line)
								s = line[12:temp_max]
								self.tree.SetItemText(child, s, 12)
						elif token[0] == "source" :
							if hole_child != None :
								self.tree.SetItemText(hole_child, token[1], 9)
						elif token[0] == "data" :
							if hole_child != None :
								self.tree.SetItemText(hole_child, token[1], 11)
						elif token[0] == "affinetable" :
							if property_child != None :
								temp_child = self.tree.AppendItem(property_child, "Table")
								self.tree.SetItemText(temp_child, "AFFINE", 1)
								self.tree.SetItemText(temp_child, token[1], 8)
								self.tree.SetItemText(temp_child, token[2], 6)
								self.tree.SetItemText(temp_child, token[3], 7)

								self.tree.SetItemText(temp_child, token[4], 2)
								if token[4] == "Enable" :
									self.tree.SetItemTextColour(temp_child, wx.BLUE)
								else :
									self.tree.SetItemTextColour(temp_child, wx.RED)
								if token_nums > 5 and  token[5] != "-" :
									self.tree.SetItemText(temp_child, token[5], 9)

								self.tree.SetItemText(temp_child, data_item + '/', 10)

						elif token[0] == "splicetable" :
							if property_child != None :
								temp_child = self.tree.AppendItem(property_child, "Table")
								self.tree.SetItemText(temp_child, "SPLICE", 1)
								self.tree.SetItemText(temp_child, token[1], 8)
								self.tree.SetItemText(temp_child, token[2], 6)
								self.tree.SetItemText(temp_child, token[3], 7)

								self.tree.SetItemText(temp_child, token[4], 2)
								if token[4] == "Enable" :
									self.tree.SetItemTextColour(temp_child, wx.BLUE)
								else :
									self.tree.SetItemTextColour(temp_child, wx.RED)
								if token_nums > 5 and token[5] != "-" :
									self.tree.SetItemText(temp_child, token[5], 9)

								self.tree.SetItemText(temp_child, data_item + '/', 10)
						elif token[0] == "eldtable" :
							if property_child != None :
								temp_child = self.tree.AppendItem(property_child, "Table")
								self.tree.SetItemText(temp_child, "ELD", 1)
								self.tree.SetItemText(temp_child, token[1], 8)
								self.tree.SetItemText(temp_child, token[2], 6)
								self.tree.SetItemText(temp_child, token[3], 7)

								self.tree.SetItemText(temp_child, token[4], 2)
								if token[4] == "Enable" :
									self.tree.SetItemTextColour(temp_child, wx.BLUE)
								else :
									self.tree.SetItemTextColour(temp_child, wx.RED)
								if token_nums > 5 and token[5] != "-" :
									self.tree.SetItemText(temp_child, token[5], 9)

								self.tree.SetItemText(temp_child, data_item + '/', 10)
						elif token[0] == "uni_culltable" :
							if property_child != None :
								temp_child = self.tree.AppendItem(property_child, "Table")
								self.tree.SetItemText(temp_child, "CULL", 1)
								self.tree.SetItemText(temp_child, token[1], 8)
								self.tree.SetItemText(temp_child, token[2], 6)
								self.tree.SetItemText(temp_child, token[3], 7)

								self.tree.SetItemText(temp_child, token[4], 2)
								if token[4] == "Enable" :
									self.tree.SetItemTextColour(temp_child, wx.BLUE)
								else :
									self.tree.SetItemTextColour(temp_child, wx.RED)
								if token_nums > 5 and token[5] != "-" :
									self.tree.SetItemText(temp_child, token[5], 9)

								self.tree.SetItemText(temp_child, data_item + '/', 10)
						elif token[0] == "eld" and token[1] == "Yes" :
							if property_child != None :
								self.tree.AppendItem(property_child, "ELD Table")
						elif token[0] == "culltable" :
							if child != None :
								temp_child = self.tree.AppendItem(child, "-Cull Table")
								self.tree.SetItemText(temp_child, token[1], 8)

								self.tree.SetItemText(temp_child, token[2], 6)
								self.tree.SetItemText(temp_child, token[3], 7)

								self.tree.SetItemText(temp_child, token[4], 2)
								if token[4] == "Enable" :
									self.tree.SetItemTextColour(temp_child, wx.BLUE)
								else :
									self.tree.SetItemTextColour(temp_child, wx.RED)
								if token_nums > 5 and token[5] != "-" :
									self.tree.SetItemText(temp_child, token[5], 9)

								self.tree.SetItemText(temp_child, data_item + '/', 10)
								self.tree.SortChildren(child)
						elif token[0] == "log" :
							if log_child != None :
								temp_child = self.tree.AppendItem(log_child, "Log Data")
								self.tree.SetItemText(temp_child, token[1], 8)
								self.tree.SetItemText(temp_child, token[2], 6)
								self.tree.SetItemText(temp_child, token[3], 7)
								self.tree.SetItemText(temp_child, token[4], 9)
								self.tree.SetItemText(temp_child, token[5], 11)

								self.tree.SetItemText(temp_child, token[6], 2)
								if token[6] == "Enable" :
									self.tree.SetItemTextColour(temp_child, wx.BLUE)
								else :
									self.tree.SetItemTextColour(temp_child, wx.RED)

								self.tree.SetItemText(temp_child, data_item + '/', 10)
								self.tree.SetItemText(temp_child, token[7], 1)
								if len(token) >= 12 :
									self.tree.SetItemText(temp_child, token[8], 4)
									self.tree.SetItemText(temp_child, token[9], 5)
									self.tree.SetItemText(temp_child, token[10], 3)
									self.tree.SetItemText(temp_child, token[11], 12)

						elif token[0] == "strat" :
							if strat_child != None :
								temp_child = self.tree.AppendItem(strat_child, token[1])
								self.tree.SetItemText(temp_child, token[2], 8)
								self.tree.SetItemText(temp_child, token[3], 6)
								self.tree.SetItemText(temp_child, token[4], 7)
								self.tree.SetItemText(temp_child, token[5], 9)
								self.tree.SetItemText(temp_child, data_item + '/', 10)
								self.tree.SetItemText(temp_child, token[6], 2)
								if token[6] == "Enable" :
									self.tree.SetItemTextColour(temp_child, wx.BLUE)
								else :
									self.tree.SetItemTextColour(temp_child, wx.RED)
						elif token[0] == "age" :
							if age_child != None :
								temp_child = self.tree.AppendItem(age_child, "Value")
								self.tree.SetItemText(temp_child, "AGE/DEPTH", 1)
								self.tree.SetItemText(temp_child, token[1], 8)
								self.tree.SetItemText(temp_child, token[2], 6)
								self.tree.SetItemText(temp_child, token[3], 7)
								self.tree.SetItemText(temp_child, token[4], 9)
								self.tree.SetItemText(temp_child, data_item + '/', 10)
								self.tree.SetItemText(temp_child, token[5], 2)
								if token[5] == "Enable" :
									self.tree.SetItemTextColour(temp_child, wx.BLUE)
								else :
									self.tree.SetItemTextColour(temp_child, wx.RED)
						elif token[0] == "series" :
							if age_child != None :
								temp_child = self.tree.AppendItem(age_child, "Model")
								self.tree.SetItemText(temp_child, "AGE", 1)
								self.tree.SetItemText(temp_child, token[1], 8)
								self.tree.SetItemText(temp_child, token[2], 6)
								self.tree.SetItemText(temp_child, token[3], 7)
								self.tree.SetItemText(temp_child, token[4], 9)
								self.tree.SetItemText(temp_child, data_item + '/', 10)
								self.tree.SetItemText(temp_child, token[5], 2)
								if token[5] == "Enable" :
									self.tree.SetItemTextColour(temp_child, wx.BLUE)
								else :
									self.tree.SetItemTextColour(temp_child, wx.RED)
						elif token[0] == "image" :
							if image_child != None :
								temp_child = self.tree.AppendItem(image_child, "Table")
								self.tree.SetItemText(temp_child, "IMAGE", 1)
								self.tree.SetItemText(temp_child, token[1], 8)
								self.tree.SetItemText(temp_child, token[2], 6)
								self.tree.SetItemText(temp_child, token[3], 7)
								self.tree.SetItemText(temp_child, token[4], 9)
								self.tree.SetItemText(temp_child, data_item + '/', 10)
								self.tree.SetItemText(temp_child, token[5], 2)
								if token[5] == "Enable" :
									self.tree.SetItemTextColour(temp_child, wx.BLUE)
								else :
									self.tree.SetItemTextColour(temp_child, wx.RED)
						elif token[0] == "secsumm":
							if secsumm_child is not None:
								self.tree.SetItemText(secsumm_child, token[1].strip(), 1)
				sub_f.close()

		loaded_item_list = []

		root_f.close()
		self.tree.SortChildren(self.root)
		self.tree.Expand(self.root)


	def OnDISMISS(self, event):
		self.Show(False)
		self.parent.midata.Check(False)
		self.parent.Window.SetFocusFromKbd()


	def changeFORMAT(self, filename, ith):
		# change format
		tempfile = self.parent.DBPath+"tmp/"
		py_correlator.formatChange(filename, tempfile)

		f = open(tempfile+"tmp.core", 'r+')
		internalith = 0
		for line in f :
			jth = 1 
			modifiedLine = line[0:-1].split()
			if modifiedLine[0] == 'null' :
				continue
			max = len(modifiedLine)
			for j in range(max) :
				if len(modifiedLine[j]) > 0 :
					self.dataPanel.SetCellValue(ith, jth, modifiedLine[j])
					jth = jth + 1
			ith = ith + 1
			internalith = internalith + 1
			if internalith >= 30  or ith >= 100 :
				break
		f.close()
		return ith


	def OnEDIT_LOG(self, event):
		self.importbtn.Enable(True)
		self.importbtn.SetLabel("Change")

		self.dataPanel.ClearGrid()
		self.OnINITGENERICSHEET()

		item = self.tree.GetSelection()
		path = self.tree.GetItemText(item, 9)
		ith = self.tree.GetItemText(item, 11)

		item = self.tree.GetItemParent(item)
		item = self.tree.GetItemParent(item)
		title = self.tree.GetItemText(item, 0)
		self.OpenLOGFILE(title, path)
		self.dataPanel.SetColLabelValue(int(ith), "Data")

		self.sideNote.SetSelection(1)


	def OnEDIT(self):
		self.importbtn.Enable(True)
		self.importbtn.SetLabel("Change")

		self.dataPanel.ClearGrid()
		self.OnINITGENERICSHEET()

		ith = 0
		type = ""
		items = self.tree.GetSelections()
		selectItem = None
		for selectItem in items :
			if self.tree.GetItemText(selectItem, 0) == "Root" :
				self.parent.OnShowMessage("Error", "Root is not allowed to select", 1)
				return False
			elif self.tree.GetItemText(selectItem, 0) == "Saved Tables" :
				self.parent.OnShowMessage("Error", "Table is not allowed to select", 1)
				return False
			else :
				if len(self.tree.GetItemText(selectItem, 8)) > 0 :
					parentItem = self.tree.GetItemParent(selectItem)
					type = self.tree.GetItemText(parentItem, 0) 

					path = self.tree.GetItemText(selectItem, 9)
					xml_flag = path.find(".xml", 0)
					if xml_flag >= 0 :
						self.handler.init()
						self.handler.openFile(self.parent.DBPath+"tmp/.tmp")
						self.parser.parse(path)
						self.handler.closeFile()
						path = self.parent.DBPath+"tmp/.tmp"

					ith = self.changeFORMAT(path, ith)

					self.selectedDataType = self.tree.GetItemText(selectItem, 1)
					end = len(self.selectedDataType) -1
					if self.selectedDataType[end] == '\n' or self.selectedDataType[end] == 'r' :
						self.selectedDataType = self.selectedDataType[0:end]
					self.selectedDataType = self.RemoveBACK(self.selectedDataType)
				else :
					type = self.tree.GetItemText(selectItem, 0)
					if type.find("-", 0) == -1 :
						totalcount = self.tree.GetChildrenCount(selectItem, False)
						if totalcount > 0 :
							child = self.tree.GetFirstChild(selectItem)
							child_item = child[0]
							selectItem = None

							if self.tree.GetItemText(child_item, 0) != "-Cull Table" :
								selectItem = child_item
								path = self.tree.GetItemText(child_item, 9)
								xml_flag = path.find(".xml", 0)
								if xml_flag >= 0 :
									self.handler.init()
									self.handler.openFile(self.parent.DBPath+"tmp/.tmp")
									self.parser.parse(path)
									self.handler.closeFile()
									path = self.parent.DBPath+"tmp/.tmp"

								ith = self.changeFORMAT(path, ith)
								self.selectedDataType = self.tree.GetItemText(child_item, 1)
								end = len(self.selectedDataType) -1
								if self.selectedDataType[end] == '\n' or self.selectedDataType[end] == 'r' :
									self.selectedDataType = self.selectedDataType[0:end]
								self.selectedDataType = self.RemoveBACK(self.selectedDataType)

							for k in range(1, totalcount) :
								child_item = self.tree.GetNextSibling(child_item)

								if self.tree.GetItemText(child_item, 0) != "-Cull Table" :
									if selectItem == None :
										selectItem = child_item
									path = self.tree.GetItemText(child_item, 9)
									xml_flag = path.find(".xml", 0)
									if xml_flag >= 0 :
										self.handler.init()
										self.handler.openFile(self.parent.DBPath+"tmp/.tmp")
										self.parser.parse(path)
										self.handler.closeFile()
										path = self.parent.DBPath+"tmp/.tmp"

									ith = self.changeFORMAT(path, ith)
					else :
						self.parent.OnShowMessage("Error", type + " is not allowed to select", 1)
						return False


		if selectItem != None :
			str_idx = self.tree.GetItemText(selectItem, 11)
			idx = str_idx[0:-1].split()
			self.UpdateDATAHEADER('')
			self.dataPanel.SetColLabelValue(int(idx[0])+1, "TopOffset")
			if idx[0] != idx[1] :
				self.dataPanel.SetColLabelValue(int(idx[1])+1, "BottomOffset")
			self.dataPanel.SetColLabelValue(int(idx[2])+1, "Depth")
			self.dataPanel.SetColLabelValue(int(idx[3])+1, "Data")
			rows = self.dataPanel.GetNumberRows()
			for i in range(rows):
				self.dataPanel.SetCellValue(i, 0, type)

		self.sideNote.SetSelection(1)


	def UpdateDATAHEADER(self, header, delim=' '):
		header = header.strip() # remove line endings
		if len(header) > 0:
			colNames = header.split(delim)
			if len(colNames) >= 2:
				colNames = [c.strip() for c in colNames] # remove any leading/trailing spaces
	
				dataFound = False
				colIdx = 1
				for c in colNames:
					if c[0].islower(): c = c.capitalize() 
					self.dataPanel.SetColLabelValue(colIdx, c)
					if c == 'Data':
						dataFound = True
					colIdx += 1
				if not dataFound:
					self.dataPanel.SetColLabelValue(colIdx - 1, "Data")
	
				# try to auto-fill data type based on last column's text
				type = ""
				typeDict = {"GRA":"Bulk Density(GRA)", "PWAVE":"Pwave", "SUSCEPTIBILITY":"Susceptibility",
							"REFLECTANCE":"Reflectance", "NATURAL":"NaturalGamma"}
				possibleType = colNames[-1].upper()
				for testStr,typeName in typeDict.items():
					if possibleType.find(testStr) != -1:
						type = typeName
						break
	                   
				rows = self.dataPanel.GetNumberRows()
				for i in range(rows):
					self.dataPanel.SetCellValue(i, 0, type)
				return 

		# couldn't parse header properly, use default columns
		self.dataPanel.SetColLabelValue(1, "Exp")
		self.dataPanel.SetColLabelValue(2, "Site")
		self.dataPanel.SetColLabelValue(3, "Hole")
		self.dataPanel.SetColLabelValue(4, "Core")
		self.dataPanel.SetColLabelValue(5, "CoreType")
		self.dataPanel.SetColLabelValue(6, "Section")
		self.dataPanel.SetColLabelValue(7, "TopOffset")


	def OnIMPORT_CULLTABLE(self, isUniversal):
		opendlg = wx.FileDialog(self, "Select a property file", self.parent.Directory, "", "*.*")
		ret = opendlg.ShowModal()
		path = opendlg.GetPath()
		source_path = path
		source_name = opendlg.GetFilename()
		self.parent.Directory = opendlg.GetDirectory()
		opendlg.Destroy()
		if ret == wx.ID_OK :
			item = self.tree.GetSelection()
			type = self.tree.GetItemText(item, 0)
			if isUniversal == True :	
				type = "universal"

			parentItem = self.tree.GetItemParent(item)
			title = self.tree.GetItemText(parentItem, 0)
			max =  len(title)
			last = title.find("-", 0)
			leg = title[0:last]
			site = title[last+1:max]
			#print "[DEBUG] leg " + leg + " site " + site

			valid = False
			siteflag = False 
			last = path.find(".xml", 0)
			if last < 0 :
				f = open(path, 'r+')
				for line in f :
					if line[0] == "#" :
						continue
					modifiedLine = line[0:-1].split(' \t')
					max = len(modifiedLine)
					if max <= 1 :
						modifiedLine = line[0:-1].split()
						if modifiedLine[0] == 'null' :
							continue
						max = len(modifiedLine)

					if max ==9 or max == 12 or max == 6 or max ==8 :
						#print "[DEBUG] " + modifiedLine[0] + " " + modifiedLine[1]
						if leg == modifiedLine[0] and modifiedLine[1].find(site, 0) >= 0 :
							siteflag = True
							valid = True 
						else :
							valid = False 
					break
				f.close()
				typeflag = True 
			else :
				self.handler.init()
				self.handler.openFile(self.parent.Directory + "/.tmp_table")
				self.parser.parse(path)
				self.handler.closeFile()
				source_name = ".tmp_table"
				path = self.parent.Directory + "/.tmp_table"
				if self.handler.type == "cull table" :
					valid = True

				if self.handler.site == site and self.handler.leg == leg :
					siteflag = True
				else :
					valid = False 

				if isUniversal == False :	
					if type != self.handler.datatype :
						print "[ERROR] Data type is different"

			if valid == True :
				filename = self.Add_CULLTABLE(item, type, isUniversal, source_path)
				if sys.platform == 'win32' :
					workingdir = os.getcwd()
					os.chdir(self.parent.Directory)
					cmd = 'copy \"' + source_name + '\" \"' + filename + '\"'
					os.system(cmd)
					#print "[DEBUG] " + cmd
					os.chdir(workingdir)
				else :
					cmd = 'cp \"' + path + '\" \"' + filename + '\"'
					os.system(cmd)

				s = "Import Cull Table: " + filename + "\n\n"
				self.parent.logFileptr.write(s)

				self.parent.OnShowMessage("Information", "Successfully imported", 1)
			elif site == True:
				self.parent.OnShowMessage("Error", "It is not cull table", 1)
			else :
				self.parent.OnShowMessage("Error", "It is not for " + title, 1)


	def OnIMPORT_TABLE(self, tableType):
		self.propertyIdx = self.tree.GetSelection()
		parentItem = self.tree.GetItemParent(self.propertyIdx)
		self.title = self.tree.GetItemText(parentItem, 0)
		self.parent.CurrentDir = self.parent.DBPath + 'db/' + self.title + '/'

		last = self.title.find('-', 0)
		max =  len(self.title)
		leg = self.title[0:last]
		site = self.title[last+1:max]
		filename = ""
		source_filename = ""
		
		siteflag = False
		type = '' 
		if tableType == 'Affine' :
			# Affine Table
			opendlg = wx.FileDialog(self, "Select a affine table file", self.parent.Directory, "", "*.*")
			ret = opendlg.ShowModal()
			path = opendlg.GetPath()
			filename = opendlg.GetFilename();
			source_filename = path
			self.parent.Directory = opendlg.GetDirectory()
			opendlg.Destroy()

			if ret == wx.ID_OK :
				last = path.find(".xml", 0)
				valid = False
				main_form = False
				if last < 0 :
					f = open(path, 'r+')
					for line in f :
						if line[0] == "#" :
							main_form = True 
							continue
						modifiedLine = line[0:-1].split()
						if modifiedLine[0] == 'null' :
							continue
						max = len(modifiedLine)
						if max == 1 :
							modifiedLine = line[0:-1].split('\t')
							max = len(modifiedLine)

						if max == 9 or max == 7 or max == 8 :
							if modifiedLine[6] == '\tY' or modifiedLine[6] == '\tN' :
								valid = True 
							elif modifiedLine[6] == 'Y' or modifiedLine[6] == 'N' :
								valid = True 
							elif modifiedLine[6] == 'Y\r' or modifiedLine[6] == 'N\r' :
								valid = True 
							elif modifiedLine[6] == '\tY\r' or modifiedLine[6] == '\tN\r' :
								valid = True 

						if leg == modifiedLine[0] and site == self.RemoveFRONTSPACE(modifiedLine[1]) :
							siteflag = True 
						else :
							valid = False 

						break
					f.close()

					if valid == True and main_form == False :
						filename = ".tmp_table"
						if sys.platform == 'win32' :
							self.OnFORMATTING(path, self.parent.Directory + "\\.tmp_table", tableType)
							path = self.parent.Directory + "\\.tmp_table"
						else :
							self.OnFORMATTING(path, self.parent.Directory + "/.tmp_table", tableType)
							path = self.parent.Directory + "/.tmp_table"

				else : # last >= 0
					self.handler.init()
					if sys.platform == 'win32' :
                                                self.handler.openFile(self.parent.Directory + "\\.tmp_table")
                                                self.parser.parse(path)
                                                path = self.parent.Directory + "\\.tmp_table"
                                        else :
                                                self.handler.openFile(self.parent.Directory + "/.tmp_table")
                                                self.parser.parse(path)
                                                path = self.parent.Directory + "/.tmp_table"
					self.handler.closeFile()
					
					filename = ".tmp_table"
					if self.handler.type == "affine table" :
						valid = True
					if self.handler.site == site and self.handler.leg == leg :
						siteflag = True
					else :
						valid = False 

				if valid == True :
					type = self.Add_TABLE('AFFINE' , 'affine', False, True, source_filename)
					self.parent.OnShowMessage("Information", "Successfully imported", 1)
				elif siteflag == True :
					self.parent.OnShowMessage("Error", "It is not affine table", 1)
				else :
					self.parent.OnShowMessage("Error", "It is not for " + self.title, 1)

		elif tableType == 'Splice' :
			# Splice Table
			opendlg = wx.FileDialog(self, "Select a splice table file", self.parent.Directory, "", "*.*")
			ret = opendlg.ShowModal()
			path = opendlg.GetPath()
			self.parent.Directory = opendlg.GetDirectory()
			filename = opendlg.GetFilename();
			source_filename = path
			opendlg.Destroy()

			if ret == wx.ID_OK :
				last = path.find(".xml", 0)
				valid = False
				main_form = False
				if last < 0 :
					f = open(path, 'r+')
					valid = False
					for line in f :
						if line[0] == "#" :
							main_form = True 
							continue
						modifiedLine = line[0:-1].split()
						if modifiedLine[0] == 'null' :
							continue
						max = len(modifiedLine)
						if max == 1 :
							modifiedLine = line[0:-1].split('\t')
							max = len(modifiedLine)

						if max == 19 :
							if modifiedLine[9] == '\tTIE' :
								valid = True 
							elif modifiedLine[9] == 'TIE' :
								valid = True 
							elif modifiedLine[9] == '\ttie' :
								valid = True 
							elif modifiedLine[9] == 'tie' :
								valid = True 
						#print "[DEBUG] " + site + " = " + modifiedLine[0] + " ? "
						if site == modifiedLine[0] :
							siteflag = True 
						else :
							valid = False 
						break
					f.close()
					if valid == True and main_form == False :
                                                filename = ".tmp_table"
                                                if sys.platform == 'win32' :
                                                        self.OnFORMATTING(path, self.parent.Directory + "\\.tmp_table", tableType)
                                                        path = self.parent.Directory + "\\.tmp_table"
                                                else :
                                                        self.OnFORMATTING(path, self.parent.Directory + "/.tmp_table", tableType)
                                                        path = self.parent.Directory + "/.tmp_table"
				else :
					self.handler.init()
					if sys.platform == 'win32' :
                                                self.handler.openFile(self.parent.Directory + "\\.tmp_table")
                                                self.parser.parse(path)
                                                path = self.parent.Directory + "\\.tmp_table"
					else :
                                                self.handler.openFile(self.parent.Directory + "/.tmp_table")
                                                self.parser.parse(path)
                                                path = self.parent.Directory + "/.tmp_table"
					self.handler.closeFile()
					
					filename = ".tmp_table"
					if self.handler.type == "splice table" :
						valid = True
					if self.handler.site == site and self.handler.leg == leg :
						siteflag = True
					else :
						valid = False 

				if valid == True :
					type = self.Add_TABLE('SPLICE' , 'splice', False, True, source_filename)
					self.parent.OnShowMessage("Information", "Successfully imported", 1)
				elif siteflag == True :
					self.parent.OnShowMessage("Error", "It is not splice table", 1)
				else :
					self.parent.OnShowMessage("Error", "It is not for " + self.title, 1)
		else :
			# ELD Table
			opendlg = wx.FileDialog(self, "Select a ELD table file", self.parent.Directory, "", "*.*")
			ret = opendlg.ShowModal()
			path = opendlg.GetPath()
			self.parent.Directory = opendlg.GetDirectory()
			filename = opendlg.GetFilename();
			source_filename = path 
			opendlg.Destroy()

			if ret == wx.ID_OK :
				last = path.find(".xml", 0)
				valid = False
				main_form = False
				if last < 0 :
					f = open(path, 'r+')
					valid = False
					for line in f :
						modifiedLine = line[0:-1].split(' \t')
						max = len(modifiedLine)
						if max == 1 :
							modifiedLine = line[0:-1].split('\t')
							max = len(modifiedLine)
							if max == 1 :
								modifiedLine = line[0:-1].split()
								if modifiedLine[0] == 'null' :
									continue
								max = len(modifiedLine)

						eld_leg = ''
						eld_site = ''
						for k in range(1, max) :
							if modifiedLine[k] == 'Leg' :
								eld_leg = modifiedLine[k+1]			
							elif modifiedLine[k] == 'Site' :
								eld_site = modifiedLine[k+1]			
								break

						if line[0] == "E" : 
							valid = True

						if eld_leg.find(leg, 0) >= 0 and eld_site.find(site,0) >= 0 : 
							siteflag = True 
						else :
							valid = False 
						break
					f.close()
					if valid == True and main_form == False :
                                                filename = ".tmp_table"
                                                if sys.platform == 'win32' :
                                                        self.OnFORMATTING(path, self.parent.Directory + "\\.tmp_table", tableType)
                                                        path = self.parent.Directory + "\\.tmp_table"
                                                else :
                                                        self.OnFORMATTING(path, self.parent.Directory + "/.tmp_table", tableType)
                                                        path = self.parent.Directory + "/.tmp_table"
				else :
					self.handler.init()
					if sys.platform == 'win32' :
                                                self.handler.openFile(self.parent.Directory + "\\.tmp_table")
                                                self.parser.parse(path)
                                                path = self.parent.Directory + "\\.tmp_table"
					else :
                                                self.handler.openFile(self.parent.Directory + "/.tmp_table")
                                                self.parser.parse(path)
                                                path = self.parent.Directory + "/.tmp_table"

					self.handler.closeFile()
					
					filename = ".tmp_table"
					if self.handler.type == "eld table" :
						valid = True
					if self.handler.site == site and self.handler.leg == leg :
						siteflag = True
					else :
						valid = False 

				if valid == True :
					type = self.Add_TABLE('ELD' , 'eld', False, True, source_filename)
					self.parent.OnShowMessage("Information", "Successfully imported", 1)
				elif siteflag == True :
					self.parent.OnShowMessage("Error", "It is not ELD table", 1)
				else :
					self.parent.OnShowMessage("Error", "It is not for " + self.title, 1)

		if type != '' :
			if sys.platform == 'win32' :
				workingdir = os.getcwd()
				os.chdir(self.parent.Directory)
				cmd = 'copy ' + filename + ' \"' + type+ '\"'	
				#print "[DEBUG] " + cmd
				os.system(cmd)
				os.chdir(workingdir)
			else :	
				cmd = 'cp \"' + path + '\" \"' + type + '\"'
				os.system(cmd)
				#print "[DEBUG] " + cmd
			self.parent.CurrentDir = ""

			s = "Import " + tableType + " Table: " + type + "\n\n"
			self.parent.logFileptr.write(s)


	def OnFORMATTING(self, source, dest, tableType):
		fin = open(source, 'r+')
		#print "[DEBUG] FORMATTING : " + source + " to " + dest
		fout = open(dest, 'w+')

		if tableType == "Affine" :
			fout.write("# Leg, Site, Hole, Core No, Section Type, Depth Offset, Y/N\n")
			fout.write("# Generated By Correlator\n")
		elif tableType == "Splice" :
			fout.write("# Site, Hole, Core No, Section Type, Section No, Top, Bottom, Mbsf, Mcd, TIE/APPEND Site, Hole, Core No, Section Type, Section No, Top, Bottom, Mbsf, Mcd\n")
			fout.write("# Generated By Correlator\n")

		for line in fin :
			max = len(line)
			if max <= 1 :
				continue
			if tableType == "ELD" :
				if line[0] == "E" or line[0] == "O" or line[0] == "A" :
					fout.write(line)
					continue

			flag = False
			for i in range(max) :
				if line[i] == ' ' :
					if flag == False :		
						flag = True 
						fout.write(" \t")
				elif line[i] == '\t' :
					if flag == False  :
						fout.write(" \t")
						flag = True 
				else :
					flag = False
					fout.write(line[i])

		fout.close()
		fin.close()


	def OnOPEN_LOG(self):
		self.importbtn.Enable(True)
		self.importbtn.SetLabel("Import")
		self.OnINITGENERICSHEET()
		self.dataPanel.ClearGrid()

		self.paths = [] 
		opendlg = wx.FileDialog(self, "Select a log file", self.parent.Directory, "", "*.*")
		ret = opendlg.ShowModal()
		path = opendlg.GetPath()
		self.parent.Directory = opendlg.GetDirectory()
		opendlg.Destroy()
		if ret == wx.ID_OK :
			item = self.tree.GetSelection()
			item = self.tree.GetItemParent(item)
			title = self.tree.GetItemText(item, 0)
			self.OpenLOGFILE(title, path)


	def OpenLOGFILE(self, title, path):
		max = len(title)
		last = title.find("-", 0)
		leg = title[0:last] 
		site = title[last+1:max] 
		row = 0 
		self.importLabel = []
		fout = open(self.parent.DBPath+"tmp/tmp.core", 'w+')
		self.paths = path 
		header_flag = False
		total_count = 0
		correaltor_flag = False

		f = open(path, 'r+')
		count =0
		for line in f :
			count += 1
			if count > 1 : 
				break
		f.seek(0, os.SEEK_SET)

		f_obj = f
		if count == 1 :
			first_line = f.readline()
			lines = first_line.split("\r")
			f_obj = lines 

		for line in f_obj :
			max = len(line)
			if max == 1 :
				continue

			last = line.find(":", 0)
			if last >= 0 :
				tokens = line.split()
				if tokens[0] == 'null' :
					continue
				type = tokens[0]
				type = type.upper()

				value = tokens[1]
				if type == "HOLE:" :
					maxvalue = len(value) 
					self.logHole = value[maxvalue-1:maxvalue]
					maxvalue = maxvalue- 1 
					value = value[0:maxvalue]
					#print "[DEBUG] Open LOG data/ SITE,HOLE : " + value + ", "  + self.logHole
					site_size = len(site)
					value_size = len(value)
					error_flag = False 
					if site_size > value_size :
						if site.find(value,0) < 0 :
							error_flag = True 
					elif site_size < value_size :
						if value.find(site, 0) < 0 :
							error_flag = True 
					else :
						if site != value :
							error_flag = True 
					if error_flag == True :
						self.parent.OnShowMessage("Error", "This log is not for " + title, 1)
						f.close()
						fout.close()
						return
					header_flag = True 
				elif type == "LEG:" or type == "EXPEDITION:" :
					maxvalue = len(value) 
					value = value[0:maxvalue]
					#print "[DEBUG] Open LOG data/ LEG : " + value
					leg_size = len(leg)
					value_size = len(value)
					error_flag = False 
					if leg_size > value_size :
						if leg.find(value, 0) < 0 :
							error_flag = True 
					elif leg_size < value_size :
						if value.find(leg, 0) < 0 :
							error_flag = True 
					else :
						if leg != value :
							error_flag = True 
					if error_flag == True :
						self.parent.OnShowMessage("Error", "This log is not for " + title, 1)
						f.close()
						fout.close()
						return
			elif line[0] == "#" : 
				modifiedLine = line[0:-1].split()
				if modifiedLine[1] == "Leg" :
					if modifiedLine[2] != "Site" :
						value = modifiedLine[2]
						#print "[DEBUG] Open LOG data/ LEG : " + value

						leg_size = len(leg)
						value_size = len(value)
						error_flag = False 
						if leg_size > value_size :
							if leg.find(value, 0) < 0 :
								error_flag = True 
						elif leg_size < value_size :
							if value.find(leg, 0) < 0 :
								error_flag = True 
						else :
							if leg != value :
								error_flag = True 
						if error_flag == True :
							self.parent.OnShowMessage("Error", "This log is not for " + title, 1)
							f.close()
							fout.close()
							return
					else :
						if modifiedLine[3] == "Depth" :
							correaltor_flag = True 
							header_flag = True 
				elif modifiedLine[1] == "Site" :
					value = modifiedLine[2]
					#print "[DEBUG] Open LOG data/ Site: " + value

					site_size = len(site)
					value_size = len(value)
					error_flag = False 
					if site_size > value_size :
						if site.find(value,0) < 0 :
							error_flag = True 
					elif site_size < value_size :
						if value.find(site, 0) < 0 :
							error_flag = True 
					else :
						if site != value :
							error_flag = True 
					if error_flag == True :
						self.parent.OnShowMessage("Error", "This log is not for " + title, 1)
						f.close()
						fout.close()
						return
				elif modifiedLine[1] == "Hole" :
					self.logHole = modifiedLine[2]
					#print "[DEBUG] Open LOG data/ HOLE : " + self.logHole
				elif modifiedLine[1] == "Type" :
					self.dataPanel.SetColLabelValue(0, "Depth")
					self.importLabel.append("Depth")  
					self.dataPanel.SetColLabelValue(1, modifiedLine[2])
					self.importLabel.append(modifiedLine[2])  
			else : 
				modifiedLine = line.split()
				first_char = "-"
				max_value = len(modifiedLine)
				if max_value > 0 :
					first_line = modifiedLine[0] 
					max_first = len(first_line)
					if max_first > 0 :
						first_char = first_line[0]

				if header_flag == False :
					if max_value <= 1 :
						continue
						
					value = modifiedLine[0]
					#print "[DEBUG] Open LOG data/ LEG: " + value
					leg_size = len(leg)
					value_size = len(value)
					error_flag = False 
					if leg_size > value_size :
						if leg.find(value, 0) < 0 :
							error_flag = True 
					elif leg_size < value_size :
						if value.find(leg, 0) < 0 :
							error_flag = True 
					else :
						if leg != value :
							error_flag = True 
					if error_flag == True :
						self.parent.OnShowMessage("Error", "This log is not for " + title, 1)
						f.close()
						fout.close()
						return

					value = modifiedLine[1]
					#print "[DEBUG] Open LOG data/ Site: " + value
					site_size = len(site)
					value_size = len(value)
					error_flag = False 
					if site_size > value_size :
						if site.find(value,0) < 0 :
							error_flag = True 
					elif site_size < value_size :
						if value.find(site, 0) < 0 :
							error_flag = True 
					else :
						if site != value :
							error_flag = True 
					if error_flag == True :
						self.parent.OnShowMessage("Error", "This log is not for " + title, 1)
						f.close()
						fout.close()
						return
					self.logHole = modifiedLine[2]
					#print "[DEBUG] Open LOG data/ HOLE : " + self.logHole
					header_flag = True
					s = ""
					order = 0
					total_count = 0
					for order in range(max_value) :
						self.dataPanel.SetCellValue(0, order, modifiedLine[order])
						s = s + str(modifiedLine[order]) + " "
						total_count += 1 
					s = s + str(modifiedLine[order]) + "\n"
					fout.write(s)
					row += 1
					#print "[DEBUG] Total number of columns = " +str(total_count)
					self.dataPanel.SetColLabelValue(0, "?")
					if max_value > 9 :
						self.dataPanel.SetColLabelValue(8, "Depth")
						for i in range(8) :
							self.importLabel.append("?")  
						self.importLabel.append("Depth")  

				elif  first_char == 'D' or first_char == 'd' :
					#print "[DEBUG] Labels : ",  modifiedLine 
					cmd_token = modifiedLine[0]
					cmd_token = cmd_token.upper()
					if cmd_token.find("DEPTH", 0) >= 0 :
						total_count = 0 
						self.dataPanel.SetColLabelValue(total_count, "Depth")
						self.importLabel.append("Depth")  
						total_count += 1

						for order in range(1, max_value) :
							if modifiedLine[order] != " " and modifiedLine[order] != "\t" and modifiedLine[order] != "" :
								self.dataPanel.SetColLabelValue(total_count, modifiedLine[order])
								self.importLabel.append(modifiedLine[order])  
								total_count += 1
					#print "[DEBUG] Total number of columns = " +str(total_count)
				elif  first_char >= 'A' and first_char <= 'z'  :
					print "[DEBUG] additional Line =" + line 
				else :

					if correaltor_flag == False  :
						if row < 120 : 
							s = ""
							count = 0
							column = 0
							for order in range(max_value) :
								if row < 120 :
									self.dataPanel.SetCellValue(row, column, modifiedLine[order])
								s = s + str(modifiedLine[order]) + " "
								count += 1 
								column += 1 
								if total_count == count :
									s = s + str(modifiedLine[order]) + "\n"
									fout.write(s)
									s = ""
									count = 0
									column = 0 
									row = row + 1
						else :
							s = ""
							max_value = max_value - 1
							for order in range(max_value) :
								s = s + str(modifiedLine[order]) + " "
							order = max_value
							s = s + str(modifiedLine[order]) + "\n"
							fout.write(s + '\n')
					else :
						modifiedLine = line.split()
						max_value = len(modifiedLine) -1
						if row < 120 : 
							s = ""
							for order in range(max_value) :
								self.dataPanel.SetCellValue(row, order, modifiedLine[order])
								s = s + str(modifiedLine[order]) + " "

							order = max_value 
							self.dataPanel.SetCellValue(row, order, modifiedLine[order])
							s = s + str(modifiedLine[order]) + "\n"
							fout.write(s)
							row = row + 1
						else :
							s = ""
							for order in range(max_value) :
								s = s + str(modifiedLine[order]) + " "
							order = max_value
							s = s + str(modifiedLine[order]) + "\n"
							fout.write(s + '\n')

		f.close()
		fout.close()

		self.importbtn.Enable(True)
		self.sideNote.SetSelection(1)

	def RemoveFRONTSPACE(self, line):
		max = len(line)
		for i in range(max) :
			if line[i] != ' ' and line[i] != '\t' and line[i] != '\r' :
				return line[i:max]
		return line 

	def RemoveBACK1(self, line):
		max = len(line) -1
		for i in range(max) :
			ith = max - i
			if line[ith] != ' ' and line[ith] != '\t' and line[ith] != '\r' and line[ith] != '\n': 
				return line[0:ith+1]
		return line 

	def RemoveBACK(self, line):
		max = len(line) -1
		for i in range(max) :
			ith = max - i
			if line[ith] != ' ' and line[ith] != '\t' and line[ith] != '\r' : 
				return line[0:ith+1]
		return line 

	def RemoveBACKSPACE(self, line):
		max = len(line)
		for i in range(max) :
			ith = max - i -1
			if line[ith] != ' ' and line[ith] != '\t' and line[ith] != '\r' : 
				return line[0:ith-1]
		return line 


	def OnOPEN(self):
		self.importbtn.Enable(True)
		self.importbtn.SetLabel("Import")
		self.OnINITGENERICSHEET()
		self.dataPanel.ClearGrid()

		self.importLabel = []
		opendlg = wx.FileDialog(self, "Select core data files", self.parent.Directory, "", "*.*", style=wx.MULTIPLE)
		ret = opendlg.ShowModal()
		self.paths = opendlg.GetPaths()
		files = opendlg.GetFilenames()
		self.parent.Directory = opendlg.GetDirectory()
		opendlg.Destroy()
		if ret == wx.ID_OK :
			ith = 0
			header = ""
			prevMax = -1
			prevHeader = ""

			# CHECK TYPE
			for i in range(len(self.paths)) :
				if i == 4 : # brgtodo 6/17/2014 why bail on 5th file? Can we only load four at a time?
					break
				path = self.paths[i]
				xml_flag = path.find(".xml", 0)
				if xml_flag >= 0 :
					self.handler.init()
					self.handler.openFile(self.parent.Directory  + "/.tmp")
					self.parser.parse(path)
					self.handler.closeFile()
					path = self.parent.Directory + "/.tmp" 

				f = open(path, 'rU')
				for line in f :
					if line[0].capitalize() in ['L', 'E']: # Leg or Exp(edition)
						header = line
					break
				if prevHeader != "" and header != prevHeader :
					f.close()
					self.parent.OnShowMessage("Error", "Column names must match exactly to import multiple files", 1)
					self.importbtn.Enable(False)
					self.OnINITGENERICSHEET()
					self.dataPanel.ClearGrid()
					return
				prevHeader = header
				f.close()

			for i in range(len(self.paths)) :
				path = self.paths[i]
				xml_flag = path.find(".xml", 0)
				if xml_flag >= 0 :
					self.handler.init()
					self.handler.openFile(self.parent.Directory  + "/.tmp")
					self.parser.parse(path)
					self.handler.closeFile()
					path = self.parent.Directory + "/.tmp" 

				header = ""
				if ith == 0 :
					f = open(path, 'rU')
					for line in f:
						if line[0].capitalize() in ['L', 'E'] :
							header = line
							break
						elif line[0] == '#':
							header = line[1:].lstrip()
							break
						else :
							break
					f.close()

				# change format
				tempfile = self.parent.DBPath+"tmp/"

				py_correlator.formatChange(path, tempfile)

				f = open(tempfile+"tmp.core", 'r+')
				internalith = 0
				for line in f :
					jth = 1 
					modifiedLine = line.split()
					max = len(modifiedLine)
					if modifiedLine[0] == "-" :
						continue
					elif modifiedLine[0] == "null" :
						continue

					if prevMax == -1 :
						prevMax = max
					elif prevMax != max :
						self.parent.OnShowMessage("Error", "Column names must match exactly to import multiple files", 1)
						self.importbtn.Enable(False)
						self.OnINITGENERICSHEET()
						self.dataPanel.ClearGrid()
						return
					for j in range(max) :
						if len(modifiedLine[j]) > 0 :
							if modifiedLine[j] != "null" :
								#print str(modifiedLine[j]) + " " + str(ith) + " " + str(jth)
								self.dataPanel.SetCellValue(ith, jth, modifiedLine[j])
								jth = jth + 1
					ith = ith + 1
					internalith = internalith + 1
					if internalith >= 30  or ith >= 100 :
						break
				f.close()

			if path.endswith('.csv'):
				delim = ','
			elif path.endswith('.tsv'):
				delim = '\t'
			else:
				delim = ' '
			
			self.UpdateDATAHEADER(header, delim)
	 		self.sideNote.SetSelection(1)


	def OnPUBLISH(self, event):
		#selectrows = self.listPanel.GetSelectedRows()
		#if len(selectrows) == 0 :
		#	self.parent.OnShowMessage("Error", "You need to select Data", 1)
		#	return

		#if self.listPanel.GetCellValue(selectrows[0], 0) == "" :
		#	self.parent.OnShowMessage("Error", "It is not data on the Data List", 1)
		#	return

		#files = self.listPanel.GetCellValue(selectrows[0], 20)
		#paths = files[0:-1].split(',')
		#path = paths[0]
		#size = len(path) -1
		#for i in range(size) : 
		#	idx = size - i
		#	if path[idx] == "/" :
		#		idx = idx + 1
		#		path = path[0:idx]
		#		break

		#prefilename = self.listPanel.GetCellValue(selectrows[0], 15)
		#size = len(prefilename) -1
		#prefilename = prefilename[0:size]

		#coretype = self.listPanel.GetCellValue(selectrows[0], 10)
		#affinetable = self.parent.DBPath + "db/" + self.listPanel.GetCellValue(selectrows[0], 15) + "/" + coretype + ".affine.table"
		#f = open(affinetable, 'r+')
		#s = f.read()
		#f.close()
		#outfile = path + prefilename + ".affine.table"
		#fout = open(outfile, 'w+')
		#fout.write(s)
		#fout.close()

		#splicetable = self.parent.DBPath +"db/" + self.listPanel.GetCellValue(selectrows[0], 15) + "/" + coretype + ".splice.table"
		#f = open(splicetable, 'r+')
		#s = f.read()
		#f.close()
		#outfile = path + prefilename + ".splice.table"
		#fout = open(outfile, 'w+')
		#fout.write(s)
		#fout.close()

		#eldtable = self.parent.DBPath + "db/" + self.listPanel.GetCellValue(selectrows[0], 15) + "/" + coretype + ".eld.table"
		#f = open(eldtable, 'r+')
		#s = f.read()
		#f.close()
		#outfile = path + prefilename + ".eld.table"
		#fout = open(outfile, 'w+')
		#fout.write(s)
		#fout.close()

		#culltable = self.parent.DBPath + "db/" + self.listPanel.GetCellValue(selectrows[0], 15) + "/" + coretype + ".cull.table"
		#f = open(culltable, 'r+')
		#s = f.read()
		#f.close()
		#outfile = path + prefilename + ".cull.table"
		#fout = open(outfile, 'w+')
		#fout.write(s)
		#fout.close()

		self.parent.OnShowMessage("Information", "All files are published", 1)


	def OnUPDATEDATA(self, selectItem, datatype):
		source = self.tree.GetItemText(selectItem, 9)
		xml_flag = source.find(".xml", 0)
		if xml_flag >= 0 :
			self.handler.init()
			self.handler.openFile(self.parent.DBPath+"tmp/.tmp")
			self.parser.parse(source)
			self.handler.closeFile()
			source = self.parent.DBPath+"tmp/.tmp"

		tempfile = self.parent.DBPath+"tmp/"
		py_correlator.formatChange(source, tempfile)

		data_line = self.tree.GetItemText(selectItem, 11)
		modifiedLine = data_line[0:-1].split()

		datasort = [ 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, -1 ]
		datasort[6] = int(modifiedLine[0]) # topoffset
		datasort[7] = int(modifiedLine[1]) # bottomoffset
		datasort[8] = int(modifiedLine[2]) # depth
		datasort[9] = int(modifiedLine[3]) # data

		tempstamp = str(datetime.today())
		last = tempstamp.find(":", 0)
		last = tempstamp.find(":", last+1)
		#stamp = tempstamp[0:10] + "," + tempstamp[12:16]
		stamp = tempstamp[0:last]

		filename = self.parent.DBPath + 'db/' + self.tree.GetItemText(selectItem, 10) + self.tree.GetItemText(selectItem, 8) 
		s = "Update Core Data: " + filename + "\n"
		self.parent.logFileptr.write(s)

		fout = open(filename, 'w+')
		s = "# " + "Exp Site Hole Core CoreType Section TopOffset BottomOffset Depth Data RunNo " + "\n"
		fout.write(s)
		s = "# " + "Data Type " + datatype + "\n"
		fout.write(s)
		s = "# " + "Updated Time " + tempstamp + "\n"
		fout.write(s)
		s = "# Generated By Correlator\n"
		fout.write(s)

		last_hole = ''
		last_core = '' 
		f = open(tempfile+"tmp.core", 'r+')
		for line in f :
			modifiedLine = line[0:-1].split()
			if modifiedLine[0] == 'null' :
				continue
			max = len(modifiedLine)
			s = ""
			if max > 3 :
				last_hole = modifiedLine[2] 
				last_core = modifiedLine[3]

			for j in range(11) :
				idx = datasort[j]
				if idx >= 0 :
					s = s + modifiedLine[idx] + " \t"
				else :
					s = s + "-" + " \t"
			s = s + "\n"
			fout.write(s)

		f.close()
		fout.close()

		type, annot = self.parent.TypeStrToInt(datatype)

		self.parent.OnNewData(None)
		self.parent.LOCK = 0
		py_correlator.openHoleFile(filename, -1, type, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, annot)
		self.parent.OnInitDataUpdate()
		self.parent.LOCK = 1
		self.parent.OnNewData(None)

		self.tree.SetItemText(selectItem, str(self.parent.min), 4)
		self.tree.SetItemText(selectItem, str(self.parent.max), 5)

		self.tree.SetItemText(selectItem, stamp, 6)
		self.tree.SetItemText(selectItem, self.parent.user, 7)

		# Check Affine/Update Affine Tables
		parentItem = self.tree.GetItemParent(selectItem)
		parentItem = self.tree.GetItemParent(parentItem)
		propertyItem = None
		type = self.tree.GetItemText(parentItem, 0)
		total = self.tree.GetChildrenCount(parentItem, False)
		if total > 0 :
			child = self.tree.GetFirstChild(parentItem)
			child_item = child[0]
			type = self.tree.GetItemText(child_item , 0)
			if type == "Saved Tables" :
				propertyItem = child_item
			else :
				for k in range(1, total) :
					child_item = self.tree.GetNextSibling(child_item)
					type = self.tree.GetItemText(child_item , 0)
					if type == "Saved Tables" :
						propertyItem = child_item
						break
		if propertyItem != None :
			total = self.tree.GetChildrenCount(propertyItem, False)
			if total > 0 :
				child = self.tree.GetFirstChild(propertyItem)
				child_item = child[0]
				if self.tree.GetItemText(child_item , 1) == 'AFFINE' :
					self.OnUPDATE_AFFINE(child_item, last_hole, last_core)
				for k in range(1, total) :
					child_item = self.tree.GetNextSibling(child_item)
					if self.tree.GetItemText(child_item , 1) == 'AFFINE' :
						self.OnUPDATE_AFFINE(child_item, last_hole, last_core)


	def OnUPDATE_AFFINE(self, item, last_hole, last_core):
		source = self.parent.DBPath + 'db/' + self.tree.GetItemText(item, 10) + self.tree.GetItemText(item, 8)
		temp_path = self.parent.DBPath + 'tmp/' 

		found = False
		fin = open(source, 'r+')
		fout = open(temp_path+"tmp.core", 'w+')
		last_core_idx = int(last_core) +1
		core_idx = last_core_idx 
		leg = ""
		site = ""
		type = ""
		offset = ""
		wrote = False 

		for line in fin :
			if line[0] == '#' :
				continue

			modifiedLine = line[0:-1].split()
			max = len(modifiedLine)
			if max > 0 :
				leg = modifiedLine[0]
				site = modifiedLine[1]

				if found == False :
					if  modifiedLine[2] == last_hole :
						core_idx = int(modifiedLine[3]) +1
						type = modifiedLine[4] 
						offset = modifiedLine[5] 
						wrote = False
						found = True 
					fout.write(line)
				elif found == True :
					if modifiedLine[2] != last_hole :
						found = False 
						print core_idx , last_core_idx
						for idx in range(core_idx,last_core_idx) :
							fout.write(leg + " \t" + site + " \t" + str(last_hole) + " \t" +  str(idx) + " \t" + type + " \t" + offset + " \tN\n")
						wrote = True 
					else :
						core_idx = int(modifiedLine[3]) +1
						type = modifiedLine[4] 
						offset = modifiedLine[5] 
						wrote = False
					fout.write(line)

		if wrote == False :
			for idx in range(core_idx,last_core_idx) :
				fout.write(leg + " \t" + site + " \t" + str(last_hole) + " \t" +  str(idx) + " \t" + type + " \t" + offset + " \tN\n")

		fin.close()
		fout.close()

		# HEEEEEEE
		if sys.platform == 'win32' :
			workingdir = os.getcwd()
			os.chdir(temp_path)
			cmd = 'copy tmp.core ' + source
			os.system(cmd)
			os.chdir(workingdir)
		else :
			cmd = 'cp \"' + temp_path + 'tmp.core\" \"' + source + '\"' 
			#print "[DEBUG] " + cmd
			os.system(cmd)


	def OnUPDATE(self):
		selectItem = self.selectedIdx
		if len(self.tree.GetItemText(selectItem, 8)) > 0 :
			# normal file
			parentItem = self.tree.GetItemParent(selectItem)
			type = self.tree.GetItemText(parentItem, 0)
			if type != "-Cull Table" :
				self.OnUPDATEDATA(selectItem, type)
				parentItem = self.tree.GetItemParent(parentItem)
				self.OnUPDATE_DB_FILE(self.tree.GetItemText(parentItem, 0), parentItem)
		else  :
			type = self.tree.GetItemText(selectItem, 0)
			if type.find("-", 0) == -1 :
				# type 
				totalcount = self.tree.GetChildrenCount(selectItem, False)
				if totalcount > 0 :
					child = self.tree.GetFirstChild(selectItem)
					child_item = child[0]
					if self.tree.GetItemText(child_item, 0) != "-Cull Table" :
						self.OnUPDATEDATA(child_item, type)
					for k in range(1, totalcount) :
						child_item = self.tree.GetNextSibling(child_item)
						if self.tree.GetItemText(child_item, 0) != "-Cull Table" :
							self.OnUPDATEDATA(child_item, type)
				parentItem = self.tree.GetItemParent(selectItem)
				self.OnUPDATE_DB_FILE(self.tree.GetItemText(parentItem, 0), parentItem)
			else :
				# leg-site
				totalcount = self.tree.GetChildrenCount(selectItem, False)
				if totalcount > 0 :
					child = self.tree.GetFirstChild(selectItem)
					child_item = child[0]
					type = self.tree.GetItemText(child_item, 0)
					if type not in STD_SITE_NODES:
						sub_totalcount = self.tree.GetChildrenCount(child_item, False)
						if sub_totalcount > 0 :
							child = self.tree.GetFirstChild(child_item)
							sub_child_item = child[0]
							if self.tree.GetItemText(sub_child_item, 0) != "-Cull Table" :
								self.OnUPDATEDATA(sub_child_item, type)
							for sub_k in range(1, sub_totalcount) :
								sub_child_item = self.tree.GetNextSibling(sub_child_item)
								if self.tree.GetItemText(sub_child_item, 0) != "-Cull Table" :
									self.OnUPDATEDATA(sub_child_item, type)
					self.OnUPDATE_DB_FILE(self.tree.GetItemText(selectItem, 0), selectItem)
					for k in range(1, totalcount) :
						child_item = self.tree.GetNextSibling(child_item)
						type = self.tree.GetItemText(child_item, 0)
						if type not in STD_SITE_NODES:
							sub_totalcount = self.tree.GetChildrenCount(child_item, False)
							if sub_totalcount > 0 :
								child = self.tree.GetFirstChild(child_item)
								sub_child_item = child[0]
								if self.tree.GetItemText(sub_child_item, 0) != "-Cull Table" :
									self.OnUPDATEDATA(sub_child_item, type)
								for sub_k in range(1, sub_totalcount) :
									sub_child_item = self.tree.GetNextSibling(sub_child_item)
									if self.tree.GetItemText(sub_child_item, 0) != "-Cull Table" :
										self.OnUPDATEDATA(sub_child_item, type)
						self.OnUPDATE_DB_FILE(self.tree.GetItemText(selectItem, 0), selectItem)

		self.parent.OnShowMessage("Information", "Successfully updated", 1)
			

	def FindItemProperty(self, item, hole):
		totalcount = self.tree.GetChildrenCount(item, False)
		if totalcount > 0 :
			child = self.tree.GetFirstChild(item)
			test_child = child[0]
			str_test = self.tree.GetItemText(test_child, 1)
			if str_test == hole and self.tree.GetItemText(test_child, 2) == 'Enable' :
				return (True, child[0])
			for k in range(1, totalcount) :
				test_child = self.tree.GetNextSibling(test_child)
				str_test = self.tree.GetItemText(test_child, 1)
				if str_test == hole and self.tree.GetItemText(test_child, 2) == 'Enable' :
					return (True, test_child)
		return (False, None)


	def FindItem(self, item, hole):
		totalcount = self.tree.GetChildrenCount(item, False)
		if totalcount > 0 :
			child = self.tree.GetFirstChild(item)
			test_child = child[0]
			str_test = self.tree.GetItemText(test_child, 0)
			if str_test == hole :
				return (True, child[0])
			for k in range(1, totalcount) :
				test_child = self.tree.GetNextSibling(test_child)
				str_test = self.tree.GetItemText(test_child, 0)
				if str_test == hole :
					return (True, test_child)
		return (False, None)


	def ImportFORMAT(self, source, dest, type, ntype, annot, stamp, datasort, selectItem):
		fout = open(self.parent.DBPath + "db/" + dest, 'w+')
		s = "# " + "Exp Site Hole Core CoreType Section TopOffset BottomOffset Depth Data RunNo " + "\n"

		fout.write(s)
		s = "# " + "Data Type " + type + "\n"
		fout.write(s)
		s = "# " + "Updated Time " + str(datetime.today()) + "\n"
		fout.write(s)
		s = "# Generated By Correlator\n"
		fout.write(s)

		temp_path = self.parent.DBPath+"tmp/"
		py_correlator.formatChange(source, temp_path)
		f = open(temp_path+"tmp.core", 'r+')
		for line in f :
			modifiedLine = line[0:-1].split()
			if modifiedLine[0] == 'null' :
				continue
			max = len(modifiedLine)
			s = ""
			for j in range(11) :
				idx = datasort[j]
				if idx >= 0 :
					s = s + modifiedLine[idx] + " \t"
				else :
					s = s + "-" + " \t"
			s = s + "\n"
			fout.write(s)
		f.close()
		fout.close()

		self.parent.LOCK = 0
		py_correlator.openHoleFile(self.parent.DBPath + "db/" + dest, -1, ntype, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, annot)
		#HYEJUNG CHANGING NOW
		self.parent.OnInitDataUpdate()
		###
		self.parent.LOCK = 1

		self.tree.SetItemText(selectItem, str(self.parent.min), 4)
		self.tree.SetItemText(selectItem, str(self.parent.max), 5)
		self.tree.SetItemText(selectItem, stamp, 6)
		self.tree.SetItemText(selectItem, str(datasort[6]) + " " + str(datasort[7]) + " " + str(datasort[8]) + " " + str(datasort[9]) + " ", 11)

		self.parent.OnNewData(None)


	def OnUPDATE_DATA(self):
		if self.currentIdx == [] : 
			return

		datatype = self.dataPanel.GetCellValue(3, 0)
		strdatatype = self.dataPanel.GetCellValue(3, 0)
		type = 7
		annot =""
		if len(datatype) == 0 :
			self.parent.OnShowMessage("Error", "You need to select data type", 1)
			return
		if datatype == "NaturalGamma" :
			datatype = "ngfix"
			type = 4
		elif datatype == "Susceptibility" :
			datatype = "susfix"
			type = 3
		elif datatype == "Reflectance" :
			datatype = "reflfix"
			type = 5
		elif datatype == "Bulk Density(GRA)" :
			datatype = "grfix"
			type = 1
		elif datatype == "Pwave" :
			datatype = "pwfix"
			type = 2
		elif datatype == "Other" :
			datatype = "otherfix"
		else :
			annot = datatype

		datasort = [ -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1 ]
		cols = self.dataPanel.GetNumberCols()
		for i in range(cols):
			if self.dataPanel.GetColLabelValue(i) == "Leg" :
				datasort[0] = i -1 
			elif self.dataPanel.GetColLabelValue(i) == "Site" :
				datasort[1] = i -1
			elif self.dataPanel.GetColLabelValue(i) == "Hole" :
				datasort[2] = i -1
			elif self.dataPanel.GetColLabelValue(i) == "Core" :
				datasort[3] = i -1
			elif self.dataPanel.GetColLabelValue(i) == "CoreType" :
				datasort[4] = i -1
			elif self.dataPanel.GetColLabelValue(i) == "Section" :
				datasort[5] = i -1
			elif self.dataPanel.GetColLabelValue(i) == "TopOffset" :
				datasort[6] = i -1
				datasort[7] = i -1
			elif self.dataPanel.GetColLabelValue(i) == "BottomOffset" :
				datasort[7] = i -1
			elif self.dataPanel.GetColLabelValue(i) == "Depth" :
				datasort[8] = i -1
			elif self.dataPanel.GetColLabelValue(i) == "Data" :
				datasort[9] = i -1
			elif self.dataPanel.GetColLabelValue(i) == "RunNo" :
				datasort[10] = i -1

		if datasort[6] == -1 :
			datasort[6] = datasort[8] 
		if datasort[7] == -1 :
			datasort[7] = datasort[8] 

		# CHECKING VALIDATION
		for ith in range(10) :
			if ith == 4 :
				continue
			if datasort[ith] == -1 :
				self.parent.OnShowMessage("Error", "Please define data column", 1)
				return

		tempstamp = str(datetime.today())
		last = tempstamp.find(":", 0)
		last = tempstamp.find(":", last+1)
		#stamp = tempstamp[0:10] + "," + tempstamp[12:16]
		stamp = tempstamp[0:last]

		self.parent.OnNewData(None)

		parentItem = None
		for selectItem in self.currentIdx :
			if len(self.tree.GetItemText(selectItem, 8)) > 0 :
				parentItem = self.tree.GetItemParent(selectItem)

				source = self.tree.GetItemText(selectItem, 9)
				xml_flag = source.find(".xml", 0)
				if xml_flag > 0 :
					self.handler.init()
					self.handler.openFile(self.parent.DBPath+"tmp/.tmp")
					self.parser.parse(source)
					self.handler.closeFile()
					source = self.parent.DBPath+"tmp/.tmp"

				filename = self.tree.GetItemText(selectItem, 8)
				s = "Update Core Data: " + filename + "\n"
				self.parent.logFileptr.write(s)

				start = filename.find('.', 0)
				filename = filename[0:start] + '.' + datatype + '.dat'
				self.tree.SetItemText(selectItem, filename, 8)
				dest = self.tree.GetItemText(selectItem, 10) + filename
				self.ImportFORMAT(source, dest, datatype, type, annot, stamp, datasort, selectItem)
				self.tree.SetItemText(selectItem, self.selectedDataType, 1)
				if self.selectedDataType == "?" :
					self.tree.SetItemText(selectItem, "Undefined", 1)
					
			else :
				titleItem = self.tree.GetItemParent(selectItem)
				title = self.tree.GetItemText(titleItem, 0)
				totalcount = self.tree.GetChildrenCount(selectItem, False)
				parentItem = selectItem 
				if totalcount > 0 :
					child = self.tree.GetFirstChild(selectItem)
					child_item = child[0]

					if self.tree.GetItemText(child_item, 0) != "-Cull Table" :
						source = self.tree.GetItemText(child_item, 9)
						xml_flag = source.find(".xml", 0)
						if xml_flag > 0 :
							self.handler.init()
							self.handler.openFile(self.parent.DBPath+"tmp/.tmp")
							self.parser.parse(source)
							self.handler.closeFile()
							source = self.parent.DBPath+"tmp/.tmp"

						filename = self.tree.GetItemText(child_item, 8)
						s = "Update Core Data: " + filename + "\n"
						self.parent.logFileptr.write(s)

						start = filename.find('.', 0)
						filename = filename[0:start] + '.' + datatype + '.dat'
						self.tree.SetItemText(child_item, filename, 8)
						dest = self.tree.GetItemText(child_item, 10) + filename
						self.ImportFORMAT(source, dest, datatype, type, annot, stamp, datasort, child_item)
						self.tree.SetItemText(child_item, self.selectedDataType, 1)
						if self.selectedDataType == "?" :
							self.tree.SetItemText(child_item, "Undefined", 1)
					else :
						filename = self.tree.GetItemText(child_item, 8)
						path = self.tree.GetItemText(child_item, 10)
						fin = open(self.parent.DBPath+ 'db/' + path + filename, 'r+')
						new_filename = str(title) + "." + str(datatype) + ".cull.table"
						if filename != new_filename :
							fout = open(self.parent.DBPath+ 'db/' + path + new_filename, 'w+')
							self.tree.SetItemText(child_item, new_filename, 8)
							for line in fin:
								max  = len(line) -1
								if max > 0 : 
									if line[0] == '#' :
										if line[0:6] == '# Type' :
											fout.write('# Type ' + str(strdatatype) + '\n')
										else :
											fout.write(line)
									else :
										fout.write(line)
							fout.close()
						fin.close()
					
					for k in range(1, totalcount) :
						child_item = self.tree.GetNextSibling(child_item)

						if self.tree.GetItemText(child_item, 0) != "-Cull Table" :
							source = self.tree.GetItemText(child_item, 9)
							xml_flag = source.find(".xml", 0)
							if xml_flag > 0 :
								self.handler.init()
								self.handler.openFile(self.parent.DBPath+"tmp/.tmp")
								self.parser.parse(source)
								self.handler.closeFile()
								source = self.parent.DBPath+"tmp/.tmp"

							filename = self.tree.GetItemText(child_item, 8)
							s = "Update Core Data: " + filename + "\n"
							self.parent.logFileptr.write(s)

							start = filename.find('.', 0)
							filename = filename[0:start] + '.' + datatype + '.dat'
							self.tree.SetItemText(child_item, filename, 8)
							dest = self.tree.GetItemText(child_item, 10) + filename
							self.ImportFORMAT(source, dest, datatype, type, annot, stamp, datasort, child_item)
							self.tree.SetItemText(child_item, self.selectedDataType, 1)
							if self.selectedDataType == "?" :
								self.tree.SetItemText(child_item, "Undefined", 1)
						else :
							filename = self.tree.GetItemText(child_item, 8)
							path = self.tree.GetItemText(child_item, 10)
							fin = open(self.parent.DBPath+ 'db/' + path + filename, 'r+')
							new_filename = str(title) + "." + str(datatype) + ".cull.table"
							if filename != new_filename :
								fout = open(self.parent.DBPath+ 'db/' + path + new_filename, 'w+')
								self.tree.SetItemText(child_item, new_filename, 8)
								for line in fin:
									max  = len(line) -1
									if max > 0 : 
										if line[0] == '#' :
											if line[0:6] == '# Type' :
												fout.write('# Type ' + str(strdatatype) + '\n')
											else :
												fout.write(line)
										else :
											fout.write(line)
								fout.close()
							fin.close()

								                               
		if parentItem != None :
			prevDataType = self.tree.GetItemText(parentItem, 0)
			if prevDataType != strdatatype :
				# different
				self.tree.SetItemText(parentItem, strdatatype, 0)

			totalcount = self.tree.GetChildrenCount(parentItem, False)
			item = parentItem
			if totalcount > 0 :
				sub_child = self.tree.GetFirstChild(item)
				item = sub_child[0]
				min = 0
				max = 0
				if self.tree.GetItemText(item, 0) == '-Cull Table' :
					cull_item = item
					for k in range(1, totalcount) :
						cull_item = self.tree.GetNextSibling(cull_item)
						if self.tree.GetItemText(cull_item, 0) != '-Cull Table' :
							min = float(self.tree.GetItemText(cull_item, 4))
							max = float(self.tree.GetItemText(cull_item, 5))
							break
				else :
					min = float(self.tree.GetItemText(item, 4))
					max = float(self.tree.GetItemText(item, 5))
  				for k in range(1, totalcount) :
					item = self.tree.GetNextSibling(item)
					if self.tree.GetItemText(item, 0) != '-Cull Table' :
						float_min = float(self.tree.GetItemText(item, 4))
						float_max = float(self.tree.GetItemText(item, 5))
						if float_min < min :
							min = float_min
						if float_max > max :
							max = float_max

				self.tree.SetItemText(parentItem, '1', 2)
				self.tree.SetItemText(parentItem, str(min), 4)
				self.tree.SetItemText(parentItem, str(max), 5)

				parentItem = self.tree.GetItemParent(parentItem)
				self.OnUPDATE_DB_FILE(self.tree.GetItemText(parentItem, 0), parentItem)

	 	self.sideNote.SetSelection(0)
	 	self.EditRow = -1
		self.importbtn.SetLabel("Import")
		self.importbtn.Enable(False)


	def OnUPDATE_LOG(self):
		cols = self.dataPanel.GetNumberCols()
		selected = -1
		for i in range(cols):
			if self.dataPanel.GetColLabelValue(i) == "Data" :
				selected = i 

		if selected == -1 :
			self.parent.OnShowMessage("Error", "You need to define Data column", 1)
			return

		item = self.tree.GetSelection()
		log_parentItem = self.tree.GetItemParent(item)
		parentItem = self.tree.GetItemParent(log_parentItem)
		title = self.tree.GetItemText(parentItem, 0)
		path = self.parent.DBPath +'db/' + title + '/'

		max = len(title)
		last = title.find("-", 0)
		leg = title[0:last]
		site = title[last+1:max]

		#filename = self.tree.GetItemText(item, 8)

		# type check and cout
		ith_file = 0
		totalcount = self.tree.GetChildrenCount(log_parentItem, False)
		if totalcount > 0 :
			child = self.tree.GetFirstChild(log_parentItem)
			child_item = child[0]
			if self.selectedDataType == self.tree.GetItemText(child_item, 1) :
				ith_file += 1
			for k in range(1, totalcount) :
				child_item = self.tree.GetNextSibling(child_item)
				if self.selectedDataType == self.tree.GetItemText(child_item, 1) :
					ith_file += 1
		if self.selectedDataType == '?' :
			self.selectedDataType = "undefined"
		filename = title + '.' + self.selectedDataType + '.' + str(ith_file) + '.log.dat'
		self.tree.SetItemText(item, filename, 8)

		fout = open(path + filename, 'w+')
		f = open(self.parent.DBPath+'tmp/tmp.core', 'r+')

		s = "Update Downhole Log Data: " + filename + "\n\n"
		self.parent.logFileptr.write(s)

		tempstamp = str(datetime.today())
		last = tempstamp.find(":", 0)
		last = tempstamp.find(":", last+1)
		#stamp = tempstamp[0:10] + "," + tempstamp[12:16]
		stamp = tempstamp[0:last]

		s = "# " + "Leg Site Depth Data" + "\n"
		fout.write(s)
		s = "# " + "Updated Time " + tempstamp + "\n"
		fout.write(s)
		s = "# " + "Site " + site + "\n"
		fout.write(s)
		s = "# " + "Leg " + leg + "\n"
		fout.write(s)
		s = "# " + "Hole " + self.logHole + "\n"
		fout.write(s)
		s = "# Generated By Correlator\n"
		fout.write(s)

		for line in f:
			max  = len(line) -1
			if max > 0 :
				line = line[0:max]
				modifiedLine = line[0:-1].split()
				if modifiedLine[0] == 'null' :
					continue
				max  = len(modifiedLine)
				if max == 1 :
					modifiedLine = line[0:-1].split('\t')

				fout.write(modifiedLine[0])

				max = len(modifiedLine)
				for i in range(1, max) :
					if i == selected : 
						fout.write(" " + modifiedLine[i] + '\n')

		f.close()
		fout.close()

		self.tree.SetItemText(item, self.selectedDataType, 1)
		self.tree.SetItemText(item, stamp, 6)
		self.tree.SetItemText(item, self.parent.user, 7)
		self.tree.SetItemText(item, str(selected), 11)

		self.parent.LOCK = 0
		py_correlator.openLogFile(path + filename, selected)
		min, max = py_correlator.getRange("Log")
		min = int(100.0 * float(min)) / 100.0;
		max = int(100.0 * float(max)) / 100.0;

		#ret = py_correlator.getData(5)
		#if ret != "" :
		#	self.parent.min = 9999.99
		#	self.parent.max = -9999.99
		#	self.parent.ParseData(ret, self.parent.Window.LogData)
		#	self.parent.Window.LogData = []
		#	py_correlator.getRange("Log")

		#	print "[DEBUG] min=" + str(self.parent.min) + " max=" + str(self.parent.max)
		self.parent.OnInitDataUpdate()
		self.parent.LOCK = 1 

		self.tree.SetItemText(item, str(min), 4)
		self.tree.SetItemText(item, str(max), 5)

		self.OnUPDATE_DB_FILE(title, parentItem)

		self.sideNote.SetSelection(0)
		self.importbtn.SetLabel("Import")
		self.importbtn.Enable(False)


	def OnIMPORT_LOG(self):
		cols = self.dataPanel.GetNumberCols()
		selected_list = [] 
		depth_no = -1
		for i in range(cols):
			if self.dataPanel.GetColLabelValue(i) == "Data" :
				selected_list.append(i)
			elif self.dataPanel.GetColLabelValue(i) == "Depth" :
				depth_no = i 

		#print "[DEBUG] Depth number is " + str(depth_no)
		if len(selected_list) == 0 :
			self.parent.OnShowMessage("Error", "You need to define Data column", 1)
			return

		item = self.tree.GetSelection()
		parentItem = self.tree.GetItemParent(item)
		title = self.tree.GetItemText(parentItem, 0)
		path = self.parent.DBPath +'db/' + title + '/'
		max = len(title)
		last = title.find("-", 0)
		leg = title[0:last]
		site = title[last+1:max]

		tempstamp = str(datetime.today())
		last = tempstamp.find(":", 0)
		last = tempstamp.find(":", last+1)
		#stamp = tempstamp[0:10] + "," + tempstamp[12:16]
		stamp = tempstamp[0:last]

		datatype = ""
		ith_file = 0
		for selected in selected_list :
			datatype = "?"
			ith = 0
			for label in self.importLabel :
				if ith == selected :
					datatype = label
					temp = datatype.split()
					datatype = temp[0]
					break
				ith = ith + 1
			if datatype == "?" :
				datatype = "undefined"

			# type check and cout
			ith_file = 0
			totalcount = self.tree.GetChildrenCount(item, False)
			if totalcount > 0 :
				child = self.tree.GetFirstChild(item)
				child_item = child[0]
				if datatype == self.tree.GetItemText(child_item, 1) :
					ith_file += 1
				for k in range(1, totalcount) :
					child_item = self.tree.GetNextSibling(child_item)
					if datatype == self.tree.GetItemText(child_item, 1) :
						ith_file += 1

			filename = title + '.' + datatype + '.' + str(ith_file) +'.log.dat' 
			if datatype == '?' :
				filename = title + '.undefined' + '.log.dat' 

			fout = open(path + filename, 'w+')
			#f = open(self.parent.DBPath+'tmp/tmp.core', 'r+')

			s = "Import Downhole Log Data: " + filename + "\n\n"
			self.parent.logFileptr.write(s)

			s = "# " + "Leg Site Depth Data" + "\n"
			fout.write(s)
			s = "# " + "Updated Time " + tempstamp + "\n"
			fout.write(s)
			s = "# " + "Site " + site + "\n"
			fout.write(s)
			s = "# " + "Leg " + leg + "\n"
			fout.write(s)
			s = "# " + "Hole " + self.logHole + "\n"
			fout.write(s)
			s = "# " + "Type " + datatype + "\n"
			fout.write(s)
			s = "# Generated By Correlator\n"
			fout.write(s)

			#f.close()
			fout.close()

			# HYEJUNG ---
			py_correlator.writeLogFile(self.parent.DBPath+'tmp/tmp.core', path + filename, depth_no, selected)

			#for line in f:
			#	max  = len(line) -1
			#	if max > 1 :
			#		line = line[0:max]
			#		modifiedLine = line[0:-1].split()
			#		if modifiedLine[0] == 'null' :
			#			continue
			#		max  = len(modifiedLine)
			#		if max == 1 :
			#			modifiedLine = line[0:-1].split('\t')
			#			max  = len(modifiedLine)

			#		if modifiedLine[0] == "" :
			#			continue

			#		for i in range(1, max) :
			#			if i == selected : 
			#				fout.write(modifiedLine[depth_no] + " " + modifiedLine[i] + '\n')
			#				print modifiedLine[i]
			#				break

			#f.close()
			#fout.close()

			newline = self.tree.AppendItem(item, 'Log Data')
			self.tree.SetItemText(newline,  filename, 8)

			if datatype == "?" :
				self.tree.SetItemText(newline, "undefined", 1)
			else :
				self.tree.SetItemText(newline, datatype, 1)

			self.tree.SetItemText(newline, "Enable", 2)
			self.tree.SetItemTextColour(newline, wx.BLUE)

			self.tree.SetItemText(newline, "1", 3)

			self.parent.LOCK = 0
			py_correlator.openLogFile(path + filename, selected)
			min, max = py_correlator.getRange("Log")
			min = int(100.0 * float(min)) / 100.0;
			max = int(100.0 * float(max)) / 100.0;

			self.parent.OnInitDataUpdate()

			self.parent.LOCK = 1 
			self.tree.SetItemText(newline, str(min), 4)
			self.tree.SetItemText(newline, str(max), 5)

			self.tree.SetItemText(newline, stamp, 6)
			self.tree.SetItemText(newline, self.parent.user, 7)
			self.tree.SetItemText(newline, self.paths, 9)
			self.tree.SetItemText(newline, title + '/', 10)
			self.tree.SetItemText(newline, str(selected), 11)

		self.OnUPDATE_DB_FILE(title, parentItem)
		self.sideNote.SetSelection(0)
		self.importbtn.Enable(False)
		self.logHole = ""


	def OnIMPORT(self, event):
		if self.importbtn.GetLabel() == "Change" :
			if self.importType == "LOG" : 
				self.OnUPDATE_LOG()
			else :
				self.OnUPDATE_DATA()
			return

		if self.importType == "LOG" : 
			self.OnIMPORT_LOG()
			return

		if len(self.paths) == 0 : 
			return

		self.parent.OnNewData(None)

		datatype = self.dataPanel.GetCellValue(3, 0)
		strdatatype = self.dataPanel.GetCellValue(3, 0)
		type = 7
		annot =""
		if len(datatype) == 0 :
			self.parent.OnShowMessage("Error", "Select a data type", 1)
			return
		if datatype == "NaturalGamma" :
			datatype = "ngfix"
			type = 4
		elif datatype == "Susceptibility" :
			datatype = "susfix"
			type = 3
		elif datatype == "Reflectance" :
			datatype = "reflfix"
			type = 5
		elif datatype == "Bulk Density(GRA)" :
			datatype = "grfix"
			type = 1
		elif datatype == "Pwave" :
			datatype = "pwfix"
			type = 2
		elif datatype == "Other" :
			datatype = "otherfix"
		else :
			type_last = len(datatype) - 1
			if datatype[type_last] == '\n' :
				datatype = datatype[0:type_last]
			annot = datatype # brg 9/17/2013 indentation was screwy here, think this is right

		datasort = [ -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1 ]
		cols = self.dataPanel.GetNumberCols()
		for i in range(cols):
			if self.dataPanel.GetColLabelValue(i) in ["Leg", "Exp"]:
				datasort[0] = i -1 
			elif self.dataPanel.GetColLabelValue(i) == "Site" :
				datasort[1] = i -1
			elif self.dataPanel.GetColLabelValue(i) == "Hole" :
				datasort[2] = i -1
			elif self.dataPanel.GetColLabelValue(i) == "Core" :
				datasort[3] = i -1
			elif self.dataPanel.GetColLabelValue(i) == "CoreType" :
				datasort[4] = i -1
			elif self.dataPanel.GetColLabelValue(i) == "Section" :
				datasort[5] = i -1
			elif self.dataPanel.GetColLabelValue(i) == "TopOffset" :
				datasort[6] = i -1
				datasort[7] = i -1
			elif self.dataPanel.GetColLabelValue(i) == "BottomOffset" :
				datasort[7] = i -1
			elif self.dataPanel.GetColLabelValue(i) == "Depth" :
				datasort[8] = i -1
			elif self.dataPanel.GetColLabelValue(i) == "Data" :
				datasort[9] = i -1
			elif self.dataPanel.GetColLabelValue(i) == "RunNo" :
				datasort[10] = i -1

		if datasort[6] == -1 :
			datasort[6] = datasort[8] 
		if datasort[7] == -1 :
			datasort[7] = datasort[8]
			
		errText = {0:"Exp (Leg)", 1:"Site", 2:"Hole", 3:"Core", 5:"Section", 6:"Depth", 7:"Depth", 8:"Depth", 9:"Data"}

		# CHECKING VALIDATION
		for ith in range(10):
			if ith == 4: # CoreType isn't required
				continue
			if datasort[ith] == -1:
				self.parent.OnShowMessage("Error", "Specify a {} column".format(errText[ith]), 1)
				return

		idx = datasort[0] +1
		leg = self.dataPanel.GetCellValue(3, idx)
		idx = datasort[1] + 1
		site = self.dataPanel.GetCellValue(3, idx)
		if leg[0] == '\t' :
			leg = leg[1:]
		if site[0] == '\t' :
			site = site[1:]
		prefilename = self.parent.DBPath + "db/" + leg + "-" + site
		if os.access(prefilename, os.F_OK) == False :
			os.mkdir(prefilename)

		filename = prefilename + "/." + datatype 
		fout = open(filename, 'w+')
		for r in datasort :
			s = str(r) + "\n"
			fout.write(s)
		fout.close()
		
		prefilename = prefilename + "/" + leg + "-" + site

		# create node on tree
		# Check leg-site node
		new = True 
		subroot = None
		child = self.tree.FindItem(self.root, leg + "-" + site) 
		if child.IsOk() == False :
			subroot = self.tree.AppendItem(self.root,  leg + "-" + site )
			self.tree.SetItemBold(subroot, True)
			self.tree.Expand(subroot)
			for nodeName in STD_SITE_NODES:
				self.tree.AppendItem(subroot, nodeName)
			child = self.tree.AppendItem(subroot, strdatatype)
			self.tree.SetItemText(child, "Continuous", 1)
			self.tree.SortChildren(subroot)

			dblist_f = open(self.parent.DBPath +'db/datalist.db', 'a+')
			dblist_f.write('\n' + leg + "-" + site)
			dblist_f.close()

		else :
			# Check data type 
			subroot = child
			ret = self.FindItem(subroot, strdatatype)
			if ret[0] == False :
				child = self.tree.AppendItem(subroot, strdatatype)
				self.tree.SetItemText(child, "Continuous", 1)
				self.tree.SortChildren(subroot)
			else :
				new = False 
				child = ret[1] 

		tempstamp = str(datetime.today())
		last = tempstamp.find(":", 0)
		last = tempstamp.find(":", last+1)
		#stamp = tempstamp[0:10] + "," + tempstamp[12:16]
		stamp = tempstamp[0:last]

		for i in range(len(self.paths)) :
			if i == 4 : # brgtodo 6/17/2014
				break

			idx = datasort[2] +1
			hole = self.dataPanel.GetCellValue(i* 30 + 3, idx)
			if hole[0] == '\t' :
				hole = hole[1:]
			filename = prefilename + "-" + hole + "." + datatype + ".dat"
			fout = open(filename, 'w+')
			s = "# " + "Exp Site Hole Core CoreType Section TopOffset BottomOffset Depth Data RunNo " + "\n"
			fout.write(s)
			s = "# " + "Data Type " + strdatatype + "\n"
			fout.write(s)
			s = "# " + "Updated Time " + str(datetime.today()) + "\n"
			fout.write(s)
			s = "# Generated By Correlator\n"
			fout.write(s)

			tempfile = self.parent.DBPath+"tmp/"
			temp_path = self.paths[i] 
			xml_flag = temp_path.find(".xml", 0)
			if xml_flag >= 0 :
				self.handler.init()
				self.handler.openFile(self.parent.Directory  + "/.tmp")
				self.parser.parse(temp_path)
				self.handler.closeFile()
				temp_path = self.parent.Directory + "/.tmp"
			py_correlator.formatChange(temp_path, tempfile)

			# MAX COLUMN TESTING
			MAX_COLUMN = 9 
			f = open(tempfile+"tmp.core", 'r+')
			for line in f :
				modifiedLine = line[0:-1].split()
				if modifiedLine[0] == 'null' :
					continue
				MAX_COLUMN = len(modifiedLine)
				MAX_COLUMN  -= 1
				if MAX_COLUMN < 9 : 
					continue
				break
			f.close()

			f = open(tempfile+"tmp.core", 'r+')
			for line in f :
				modifiedLine = line[0:-1].split()
				if modifiedLine[0] == 'null' :
					continue
				max = len(modifiedLine)
				s = ""
				if max <= MAX_COLUMN :
					continue;
				if modifiedLine[MAX_COLUMN].find("null", 0) >= 0 :
					continue
				else :
					for j in range(11) :
						idx = datasort[j]
						if idx > MAX_COLUMN :
							continue
						if idx >= 0 :
							s = s + modifiedLine[idx] + " "
						else :
							s = s + "-" + " "
					s = s + "\n"
					fout.write(s)
			f.close()
			fout.close()

			# Check hole
			ret = self.FindItem(child, hole)
			if ret[0] == True :
				# if there is same hole, then it's error
				self.parent.OnShowMessage("Error", "{} already has {} data for Hole {}".format(leg + '-' + site, strdatatype, hole), 1)
				break
			else :
				self.parent.LOCK = 0	
				py_correlator.openHoleFile(filename, -1, type, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, annot)
				#HYEJUNG CHANGING NOW
				self.parent.OnInitDataUpdate()
				### 
				self.parent.LOCK = 1	

				s = "Import Core Data: " + filename + "\n"
				self.parent.logFileptr.write(s)

				newline = self.tree.AppendItem(child, hole)
				self.tree.SetItemText(newline, leg + "-" + site + "-" + hole + "." + datatype + ".dat", 8)

				self.tree.SetItemText(newline, "1", 3)
				self.tree.SetItemText(newline, "Enable", 2)
				self.tree.SetItemText(newline, str(self.parent.min), 4)
				self.tree.SetItemText(newline, str(self.parent.max), 5)
				self.tree.SetItemText(newline, stamp, 6)
				self.tree.SetItemText(newline, self.parent.user, 7)
				self.tree.SetItemText(newline, self.paths[i], 9)
				self.tree.SetItemText(newline, leg + "-" + site + "/", 10)
				self.tree.SetItemText(newline, str(datasort[6]) + " " + str(datasort[7]) + " " + str(datasort[8]) + " " + str(datasort[9]) + " ", 11)
				self.tree.SetItemText(newline, self.selectedDataType, 1)
				if self.selectedDataType == "?" :
					self.tree.SetItemText(newline, "Undefined", 1)
				self.tree.SetItemText(newline, self.selectedDepthType, 13)
				

				self.parent.OnNewData(None)


		self.parent.logFileptr.write("\n")

		self.tree.SortChildren(child)
		self.tree.SortChildren(self.root)

		item = child
		totalcount = self.tree.GetChildrenCount(item, False)
		if totalcount > 0 :
			sub_child = self.tree.GetFirstChild(item)
			item = sub_child[0]
			min = float(self.tree.GetItemText(item, 4))
			max = float(self.tree.GetItemText(item, 5))
  			for k in range(1, totalcount) :
				item = self.tree.GetNextSibling(item)
				float_min = float(self.tree.GetItemText(item, 4))
				float_max = float(self.tree.GetItemText(item, 5))
				if float_min < min :
					min = float_min
				if float_max > max :
					max = float_max

			item = child
			self.tree.SetItemText(item, '1', 3)
			self.tree.SetItemText(item, str(min), 4)
			self.tree.SetItemText(item, str(max), 5)

			self.OnUPDATE_DB_FILE(leg + "-" + site, subroot)

	 	self.sideNote.SetSelection(0)
	 	self.EditRow = -1
		self.importbtn.Enable(False)


	def OnSELECTCELL(self, event) :
		self.selectedCol = event.GetCol()
		pos = event.GetPosition()

		if self.importType == "LOG" :
			popupMenu = wx.Menu()
			popupMenu.Append(14, "&Depth")
			wx.EVT_MENU(popupMenu, 14, self.OnCHANGELABEL)
			popupMenu.Append(1, "&Data")
			wx.EVT_MENU(popupMenu, 1, self.OnCHANGELABEL)
			popupMenu.Append(13, "&Unselect")
			wx.EVT_MENU(popupMenu, 13, self.OnCHANGELABEL)
			self.PopupMenu(popupMenu, pos)
		elif self.selectedCol >= 1 :
			if self.importType != "LOG" :
				popupMenu = wx.Menu()
				popupMenu.Append(1, "&Data")
				wx.EVT_MENU(popupMenu, 1, self.OnCHANGELABEL)
				popupMenu.Append(2, "&Depth")
				wx.EVT_MENU(popupMenu, 2, self.OnCHANGELABEL)
				popupMenu.Append(3, "&?")
				wx.EVT_MENU(popupMenu, 3, self.OnCHANGELABEL)
				popupMenu.Append(4, "&Exp")
				wx.EVT_MENU(popupMenu, 4, self.OnCHANGELABEL)
				popupMenu.Append(5, "&Site")
				wx.EVT_MENU(popupMenu, 5, self.OnCHANGELABEL)
				popupMenu.Append(6, "&Hole")
				wx.EVT_MENU(popupMenu, 6, self.OnCHANGELABEL)
				popupMenu.Append(7, "&Core")
				wx.EVT_MENU(popupMenu, 7, self.OnCHANGELABEL)
				popupMenu.Append(8, "&CoreType")
				wx.EVT_MENU(popupMenu, 8, self.OnCHANGELABEL)
				popupMenu.Append(9, "&Section")
				wx.EVT_MENU(popupMenu, 9, self.OnCHANGELABEL)
				popupMenu.Append(10, "&TopOffset")
				wx.EVT_MENU(popupMenu, 10, self.OnCHANGELABEL)
				popupMenu.Append(11, "&BottomOffset")
				wx.EVT_MENU(popupMenu, 11, self.OnCHANGELABEL)
				popupMenu.Append(12, "&RunNo")
				wx.EVT_MENU(popupMenu, 12, self.OnCHANGELABEL)
				
				if self.dataPanel.GetColLabelValue(self.selectedCol) in ["Leg", "Exp"]:
					popupMenu.AppendSeparator()
					popupMenu.Append(101, "&Edit Exp/Leg...")
					wx.EVT_MENU(popupMenu, 101, self.OnCHANGENUMBER)
					#self.PopupMenu(popupMenu, pos)
				elif self.dataPanel.GetColLabelValue(self.selectedCol) == "Site":
					popupMenu.AppendSeparator()
					popupMenu.Append(102, "&Edit Site...")
					wx.EVT_MENU(popupMenu, 102, self.OnCHANGENUMBER)
					
				self.PopupMenu(popupMenu, pos)

#		elif self.selectedCol == 1 and self.importType != "LOG" : 
#			popupMenu = wx.Menu()
#			popupMenu.Append(1, "&Edit Leg No")
#			wx.EVT_MENU(popupMenu, 1, self.OnCHANGENUMBER)
#			self.PopupMenu(popupMenu, pos)
#		elif self.selectedCol == 2 and self.importType != "LOG" : 
#			popupMenu = wx.Menu()
#			popupMenu.Append(2, "&Edit Site No")
#			wx.EVT_MENU(popupMenu, 2, self.OnCHANGENUMBER)
#			self.PopupMenu(popupMenu, pos)
		else :
#			#if self.importbtn.GetLabel() == "Change" or self.importType == "LOG" :
#			if self.importType == "LOG" :
#				return
			popupMenu = wx.Menu()
			popupMenu.Append(1, "&NaturalGamma")
			wx.EVT_MENU(popupMenu, 1, self.OnCHANGETYPE)
			popupMenu.Append(2, "&Susceptibility")
			wx.EVT_MENU(popupMenu, 2, self.OnCHANGETYPE)
			popupMenu.Append(3, "&Reflectance")
			wx.EVT_MENU(popupMenu, 3, self.OnCHANGETYPE)
			popupMenu.Append(4, "&Bulk Density(GRA)")
			wx.EVT_MENU(popupMenu, 4, self.OnCHANGETYPE)
			popupMenu.Append(5, "&Pwave")
			wx.EVT_MENU(popupMenu, 5, self.OnCHANGETYPE)

			#popupMenu.Append(6, "&Other")
			#wx.EVT_MENU(popupMenu, 6, self.OnCHANGETYPE)

			#----- HYEJUNG
			filename =  self.parent.DBPath + 'tmp/datatypelist.cfg' 
			if os.access(filename, os.F_OK) == True :
				f = open(filename, 'r+')
				idx = 8
				for line in f :
					line_max = len(line)
					if line_max == 1 :
						continue

					type_last = line_max -1
                                        if line[type_last] == '\n' :
                                                line = line[0:type_last]
                                
					popupMenu.Append(idx, "&"+ line)
					wx.EVT_MENU(popupMenu, idx, self.OnCHANGETYPE)
					idx = idx + 1
				f.close()
			#----- HYEJUNG
			
			popupMenu.Append(7, "&User define")
			wx.EVT_MENU(popupMenu, 7, self.OnCHANGETYPE)
			self.PopupMenu(popupMenu, pos)


	def OnCHANGETYPE(self, event) :
		opId = event.GetId()
		datatype = ""
		if opId == 1 :
			datatype = "NaturalGamma"
		elif opId == 2 :
			datatype = "Susceptibility"
		elif opId == 3 :
			datatype = "Reflectance"
		elif opId == 4 :
			datatype = "Bulk Density(GRA)"
		elif opId == 5 :
			datatype = "Pwave"
		elif opId == 6 :
			datatype = "Other"
		elif opId == 7 :
			while True :
				dlg = dialog.BoxDialog(self, "User define data type")
				ret = dlg.ShowModal()
				datatype = ""
				if ret == wx.ID_OK :
					datatype = dlg.txt.GetValue() 
					if datatype.find("-", 0) >= 0 :
						self.parent.OnShowMessage("Error", "Hyphen(-) is not allowed", 1)
					else :
						if dlg.register.GetValue() == True : 
                                                        type_last = len(datatype) -1
                                                        if datatype[type_last] == '\n' :
                                                                datatype = datatype[0:type_last]
                                                                        
							# check whether there is same datatype 
							filename =  self.parent.DBPath + 'tmp/datatypelist.cfg'
							if os.access(filename, os.F_OK) == False :
								fout = open(filename, 'w+')
								fout.write('\n' + datatype)
								fout.close()
							else :
								f = open(filename, 'r+')
								flag = False
								token = '' 
								for line in f :
									max = len(line)
									if max == 1 :
										continue

									token = line[0:max]
									if line[max-1:max] == '\n' :
										token = line[0:max-1]
									if token == datatype :
										flag = True
										break
								f.close()
								if flag == False :
									fout = open(filename, 'a+')
									fout.write('\n' + datatype)
									fout.close()
						break
				else :
					break
				#dlg.Destory()
			else :
				#dlg.Destory()
				return	
		else :
			event_obj = event.GetEventObject()
			line = event_obj.GetLabel(opId)
			max = len(line)
			datatype = line[1:max]
			#datatype = dlg.txt.GetValue() 

		if self.importbtn.GetLabel() == "Change" :
			# need to check other data type 
			parentItem = None
			for selectItem in self.currentIdx :
				if len(self.tree.GetItemText(selectItem, 8)) > 0 :
					parentItem = self.tree.GetItemParent(selectItem)
				else : 
					parentItem = selectItem
				break
			if parentItem != None :
				currentItem = parentItem
				parentItem = self.tree.GetItemParent(parentItem)

				totalcount = self.tree.GetChildrenCount(parentItem, False)
				if totalcount > 0 :
					child = self.tree.GetFirstChild(parentItem)
					child_item = child[0]
					if currentItem != child_item and datatype  == self.tree.GetItemText(child_item, 0) :
						self.parent.OnShowMessage("Error", "Same data type is already imported", 1)
						return
					for k in range(1, totalcount) :
						child_item = self.tree.GetNextSibling(child_item)
						if currentItem != child_item and datatype  == self.tree.GetItemText(child_item, 0) :
							self.parent.OnShowMessage("Error", "Same data type is already imported", 1)
							return

		rows = self.dataPanel.GetNumberRows()
		for i in range(rows):
			self.dataPanel.SetCellValue(i, 0, datatype)


	def OnCHANGENUMBER(self, event) :
		opId = event.GetId()
		col = self.selectedCol
		flag = False
		if opId == 1 or opId == 101:
			dlg = dialog.EditBoxDialog(self, "Leg Number")
			ret = dlg.ShowModal()
			if ret == wx.ID_OK :
				flag = True 
				num = dlg.txt.GetValue()
				rows = self.dataPanel.GetNumberRows()
				for i in range(rows):
					self.dataPanel.SetCellValue(i, col, num)
		elif opId == 2 or opId == 102 :
			dlg = dialog.EditBoxDialog(self, "Site Number")
			ret = dlg.ShowModal()
			if ret == wx.ID_OK :
				flag = True 
				num = dlg.txt.GetValue()
				rows = self.dataPanel.GetNumberRows()
				for i in range(rows):
					self.dataPanel.SetCellValue(i, col, num)


	def OnCHANGELABEL(self, event) :
		opId = event.GetId()

		#if self.importType == "CORE" :

		mode = self.importbtn.GetLabel()
		# F1 
		ith = 0
		if self.importType != "LOG" or mode == "Change" :
			for label in self.importLabel :
				self.dataPanel.SetColLabelValue(ith, label)
				ith = ith + 1

		if opId == 1 :
			self.selectedDataType = self.dataPanel.GetColLabelValue(self.selectedCol)
 			end = len(self.selectedDataType) -1
			if self.selectedDataType[end] == '\n' or self.selectedDataType[end] == '\r' :
				self.selectedDataType = self.selectedDataType[0:end]
			self.selectedDataType = self.RemoveBACK(self.selectedDataType)

			self.dataPanel.SetColLabelValue(self.selectedCol, "Data")
		elif opId == 2 :
			self.selectedDepthType = self.dataPanel.GetColLabelValue(self.selectedCol)
 			end = len(self.selectedDepthType) -1
			if self.selectedDepthType[end] == '\n' or self.selectedDepthType[end] == '\r' :
				self.selectedDepthType = self.selectedDepthType[0:end]
			self.selectedDepthType = self.RemoveBACK(self.selectedDepthType)
			self.dataPanel.SetColLabelValue(self.selectedCol, "Depth")
		elif opId == 3 :
			self.dataPanel.SetColLabelValue(self.selectedCol, "?")
		elif opId == 4 :
			self.dataPanel.SetColLabelValue(self.selectedCol, "Exp")
		elif opId == 5 :
			self.dataPanel.SetColLabelValue(self.selectedCol, "Site")
		elif opId == 6 :
			self.dataPanel.SetColLabelValue(self.selectedCol, "Hole")
		elif opId == 7 :
			self.dataPanel.SetColLabelValue(self.selectedCol, "Core")
		elif opId == 8 :
			self.dataPanel.SetColLabelValue(self.selectedCol, "CoreType")
		elif opId == 9:
			self.dataPanel.SetColLabelValue(self.selectedCol, "Section")
		elif opId == 10 :
			self.dataPanel.SetColLabelValue(self.selectedCol, "TopOffset")
		elif opId == 11 :
			self.dataPanel.SetColLabelValue(self.selectedCol, "BottomOffset")
		elif opId == 12 :
			self.dataPanel.SetColLabelValue(self.selectedCol, "RunNo")
		elif opId == 13 :
			origin_label = ""
			ith = 0 
			for label in self.importLabel :
				if ith == self.selectedCol :
					origin_label = label 
					break
				ith = ith + 1
			self.dataPanel.SetColLabelValue(self.selectedCol, origin_label)
		elif opId == 14 :
			self.dataPanel.SetColLabelValue(self.selectedCol, "Depth")

		self.selectedCol = -1

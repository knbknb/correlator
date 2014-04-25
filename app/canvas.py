#_!/usr/bin/env python

## For Mac-OSX
#/usr/bin/env pythonw
import platform
platform_name = platform.uname()

import wx 
import wx.lib.sheet as sheet
from wx.lib import plot
from datetime import datetime
import random, sys, os, re, time, ConfigParser, string

from importManager import py_correlator

import frames

# brg 4/9/2014: Why are we defining our own wxBufferedWindow when
# wx.BufferedWindow already exists (same interface 'n all) in wx?
class wxBufferedWindow(wx.Window):

	"""

	A Buffered window class.

	To use it, subclass it and define a Draw(DC) method that takes a DC
	to draw to. In that method, put the code needed to draw the picture
	you want. The window will automatically be double buffered, and the
	screen will be automatically updated when a Paint event is received.

	When the drawing needs to change, you app needs to call the
	UpdateDrawing() method.

	"""
	def __init__(self, parent, id,
				 pos=wx.DefaultPosition,
				 size=wx.DefaultSize,
				 style=wx.NO_FULL_REPAINT_ON_RESIZE):
		wx.Window.__init__(self, parent, id, pos, size, style)
		#wx.SplitterWindow.__init__(self, parent, id, pos, size, style)

		self.sideTabSize = 340 
		self.CLOSEFLAG = 0 

		self.WindowUpdate = 0
		wx.EVT_PAINT(self, self.OnPaint)
		wx.EVT_SIZE(self, self.OnSize)

		# OnSize called to make sure the buffer is initialized.
		# This might result in OnSize getting called twice on some
		# platforms at initialization, but little harm done.
		self.OnSize(None)

	def Draw(self, dc):
		## just here as a place holder.
		## This method should be over-ridden when sub-classed
		pass

	def OnPaint(self, event):
		# All that is needed here is to draw the buffer to screen
		dc = wx.PaintDC(self)
		dc.DrawBitmap(self._Buffer, 0, 0)

	def OnSize(self, event):
		# The Buffer init is done here, to make sure the buffer is always
		# the same size as the Window
		self.Width, self.Height = self.GetClientSizeTuple()
				
		if self.CLOSEFLAG == 1 :
			self.Width = self.Width - 45 
		else :
			self.Width = self.Width - self.sideTabSize
		self.WindowUpdate = 1

		# Make new off screen bitmap: this bitmap will always have the
		# current drawing in it, so it can be used to save the image to
		# a file, or whatever.
		if self.Width > 0 and self.Height > 0 :
			self._Buffer = wx.EmptyBitmap(self.Width, self.Height)
			self.UpdateDrawing()

	def UpdateDrawing(self):
		"""
		This would get called if the drawing needed to change, for whatever reason.

		The idea here is that the drawing is based on some data generated
		elsewhere in the system. IF that data changes, the drawing needs to
		be updated.

		"""
		# update the buffer
		dc = wx.MemoryDC()
		dc.SelectObject(self._Buffer)
		
		self.Draw(dc)
		# update the screen
		wx.ClientDC(self).Blit(0, 0, self.Width, self.Height, dc, 0, 0)


class DataCanvas(wxBufferedWindow):
	def __init__(self, parent, id= -1):
		## Any data the Draw() function needs must be initialized before
		## calling wxBufferedWindow.__init__, as it will call the Draw
		## function.

		self.bitmaps = {}
		if platform_name[0] == "Windows" :
			self.font1 = wx.Font(12, wx.SWISS, wx.NORMAL, wx.BOLD)
			self.font2 = wx.Font(9, wx.SWISS, wx.NORMAL, wx.NORMAL)
			self.font3 = wx.Font(9, wx.SWISS, wx.NORMAL, wx.BOLD)
		else :
			self.font1 = wx.Font(14, wx.TELETYPE, wx.NORMAL, wx.BOLD)
			self.font2 = wx.Font(10, wx.TELETYPE, wx.NORMAL, wx.BOLD)
			self.font3 = wx.Font(9, wx.TELETYPE, wx.NORMAL, wx.BOLD)
					
		self.parent = parent
		self.DrawData = {}
		self.Highlight_Tie = -1
		self.SpliceTieFromFile = 0
		self.LogTieList = []
		self.ShiftTieList = []
		self.ShiftClue = True 
		self.LogClue = True 
		self.Floating = False 
		self.hole_sagan = -1 
		self.sagan_type = "" 
		self.fg = wx.Colour(255, 255, 255)
		# 1 = Composite, 2 = Splice, 3 = Sagan
		self.mode = 1 
		self.statusStr = "Composite"
		self.ShowSplice = True
		self.currentHole = -1
		self.showMenu = False
		self.showGrid = False
		self.showHoleGrid = True
		self.ShowStrat = True
		self.ShowLog = False 
		self.WidthsControl = []
		self.Done = False
		self.minScrollRange = 0
		self.smooth_id = 0
		self.selectedType = ""
		self.ScrollSize = 15
		self.AgeSpliceHole = True
		self.maxAgeRange = 8.0 
		# range_start, range_stop, rate, offset
		self.PreviewLog = [-1, -1, 1.0, 0, -1, -1, 1.0]
		self.PreviewOffset = 0
		self.PreviewB = 0
		self.PreviewBOffset = 0
		self.PreviewNumTies = 0
		self.PreviewFirstNo = 0
		self.prevNoteId = -1
		self.DiscretePlotMode = 0 
		self.DiscretetSize = 1 
		self.altType = ""
		self.altMultipleType = False

		# 0 , 1 - Composite, 2 - Splice
		self.Process = 0 
		self.Constrained = 1 
		self.isSecondScroll = 1 # if 1, composite and splice windows scroll separately
		self.isSecondScrollBackup = 1 # appears to backup isSecondScroll value 
		self.ScrollUpdate = 0
		self.isLogMode = 0 
		self.closeFlag = True 
		#self.note_id = 0
		self.LogAutoMode = 1
		self.isAppend = False 
		self.SPSelectedCore = -1 
		self.SpliceDiff = 2
		self.MainViewMode = True
		self.mbsfDepthPlot = 0 
		self.firstPntAge = 0.0
		self.firstPntDepth = 0.0
		self.SelectedAge = -1
		self.AgeDataList = []
		self.maxSPcore = 0
		self.AgeYRates = []
		self.AgeEnableDrag = 0
		self.AgeShiftX = 0
		self.AgeShiftY = 0
		self.AgeUnit = 0.1
		self.AgeOffset = 0.0
		self.AdjustAgeDepth = 0.0
		self.prevDepth = 0.0
		self.AgeSpliceGap = 2.0
		self.lastLogTie = -1 
		self.LDselectedTie = -1
		self.SaganDots = []
		self.ShowAutoPanel = False
		self.ELDapplied = False 
		self.MousePos = None 

		# Use dictionary so we can name colors - also need a list of names since dictionary is unordered
		self.colorDictKeys = [ 'mbsf', 'mcd', 'eld', 'smooth', 'splice', 'log', 'mudlineAdjust', \
								'fixedTie', 'shiftTie', 'paleomag', 'diatom', 'rad', 'foram', \
								'nano', 'background', 'foreground', 'corrWindow', 'guide' ] 
		self.colorDict = { 'mbsf': wx.Colour(238, 238, 0), 'mcd': wx.Colour(0, 139, 0), \
							'eld': wx.Colour(0, 255, 255), 'smooth': wx.Colour(238, 216, 174), \
							'splice': wx.Colour(30, 144, 255), 'log': wx.Colour(64, 224, 208), \
							'mudlineAdjust': wx.Colour(0, 255, 0), 'fixedTie': wx.Colour(139, 0, 0), \
							'shiftTie': wx.Colour(0, 139, 0), 'paleomag': wx.Colour(30, 144, 255), \
							'diatom': wx.Colour(218, 165, 32), 'rad': wx.Colour(147, 112, 219), \
							'foram': wx.Colour(84, 139, 84), 'nano': wx.Colour(219, 112, 147), \
							'background': wx.Colour(0, 0, 0), 'foreground': wx.Colour(255, 255, 255), \
							'corrWindow': wx.Colour(178, 34, 34), 'guide': wx.Colour(224, 255, 255) }
		
		# mbsf, mcd, eld, smooth, splice, log, mudline adjust, fixed tie, shift tie
		# paleomag, diatom, rad, foram, nano
		self.colorList = [ wx.Colour(238, 238, 0), wx.Colour(0, 139, 0), \
			wx.Colour(0, 255, 255), wx.Colour(238, 216, 174), wx.Colour(30, 144, 255), \
			wx.Colour(64, 224, 208), wx.Colour(0, 255, 0), wx.Colour(139, 0, 0), \
			wx.Colour(0, 139, 0), wx.Colour(30, 144, 255), wx.Colour(218, 165, 32), \
			wx.Colour(147, 112, 219), wx.Colour(84, 139, 84), wx.Colour(219, 112, 147), \
			wx.Colour(0, 0, 0), wx.Colour(255, 255, 255), \
			wx.Colour(178, 34, 34), wx.Colour(224, 255, 255)] 

		self.overlapcolorList = [ wx.Colour(238, 0, 0), wx.Colour(0, 139, 0), \
				wx.Colour(0, 255, 255), wx.Colour(238, 216, 174), wx.Colour(30, 144, 255), \
				wx.Colour(147, 112, 219), wx.Colour(84, 139, 84), wx.Colour(219, 112, 147), \
				wx.Colour(30, 144, 255)]

		self.compositeX = 35
		self.splicerX = 695
		self.splicerBackX = 695
		self.tieline_width = 1

		self.holeWidth = 300
		self.spliceHoleWidth = 300
		self.logHoleWidth = 210
		
		self.startDepth = 60.0
		self.rulerHeight = 0 
		self.rulerStartDepth = 0.0 
		self.rulerEndDepth = 0.0
		self.rulerTickRate = 0.0 
		self.rulerUnits = 'cm' # one of 'm','cm','mm'
		self.tieDotSize = 10 

		self.ageXGap = 1.0
		self.ageLength = 90.0
		self.startAgeDepth = 60.0
		self.rulerStartAgeDepth = 0.0 
		self.rulerEndAgeDepth = 0.0
		self.ageRulerTickRate = 0.0 

		self.coefRange = 0.0
		self.coefRangeSplice = 0.0
		self.datascale = 0
		self.bothscale = 0
		self.isLogShifted = False
		#self.lastSpliceX = -1
		#self.lastSpliceY = -1

		self.decimateEnable = 0
		self.smoothEnable = 0
		self.cullEnable = 0
		self.autocoreNo = [] 

		# type, min, max, coef, smooth_mode, continous_type[True/False]
		self.range = [] 
		self.continue_flag = True 
		self.timeseries_flag = False 

		self.minRange = -1
		self.minAgeRange = 0.0 
		self.minRangeSplice = -1
		self.maxRange = -1
		self.SPrulerHeight = 0 
		self.SPrulerStartDepth = 0.0 
		self.SPrulerEndDepth = 0.0 
		self.SPrulerStartAgeDepth = 0.0 

		# number of pixels between labeled depth scale ticks, currently 2.0m, 
		# thus ( self.length / self.gap ) / 2 gives pixels/meter
		self.length = 60 
		
		self.ageYLength = 60
		self.spliceYLength = 60

		# meters between labeled depth scale ticks - appears to be constant
		self.gap = 2
		
		self.ageGap = 10 

		self.HoleCount = 0
		self.selectScroll = 0
		self.grabCore = -1
		self.SPgrabCore = -1
		self.spliceTie = -1
		self.logTie = -1
		self.splice_smooth_flag = 0 

		self.squishValue = 100
		self.squishCoreId = -1 

		self.HoleData = []
		self.SectionData = []
		self.SmoothData = [] 
		self.TieData = [] 
		self.StratData = []
		self.UserdefStratData = []
		self.AdjustDepthCore = []
		self.GuideCore = []
		self.SpliceSmoothData = []

		self.LogData = [] 
		self.LogSMData = [] 

		self.FirstDepth = -999.99
		self.SpliceCoreId = -1 
		self.SplicedHole = []
		self.SpliceTieData = [] # splice tie
		self.RealSpliceTie = []	 # splice tie
		self.SPGuideCore = []	# splice guide 
		self.SpliceCore = []	 # core numbers in splice region
		self.SpliceData = []
		self.AltSpliceData = []
		self.LogSpliceData = []
		self.LogSpliceSmoothData = []
		self.LogTieData = [] # splice tie
		self.spliceCount = 0
		self.begin_append = False 
		self.CurrentSpliceCore = -1
		self.PreviousSpliceCore = -1

		self.drag = 0
		self.selectedCore = -1 
		self.LogselectedCore = -1 
		self.selectedTie = -1 
		self.activeTie = -1 
		self.activeSPTie = -1 
		self.activeSATie = -1 
		self.activeCore = -1 
		self.shift_range = 0.1 

		self.compositeDepth = -1
		self.spliceDepth = -1
		self.saganDepth = -1
		self.selectedLastTie = -1 
		self.SPselectedTie = -1 
		self.SPselectedLastTie = -1 
		self.LogselectedTie = -1 
		self.mouseX = 0 
		self.mouseY = 0 
		self.newHoleX = 30.0
		self.guideCore = -1
		self.guideSPCore = -1
		self.minData = -1
		self.coreCount = 0 
		self.pressedkeyShift = 0
		self.pressedkeyS = 0
		self.pressedkeyD = 0
		self.selectedHoleType = "" 
		self.selectedStartX = 0 
		self.selectedCount = 0
		self.hideTie = 0
		self.currentStartX = 0
		self.grabScrollA = 0 
		self.grabScrollB = 0 
		self.grabScrollC = 0 
		self.Lock = False

		self.spliceWindowOn = 1
		wxBufferedWindow.__init__(self, parent, id)

		self.sidePanel = wx.Panel(self, -1)
		self.sidePanel.SetBackgroundColour(wx.Colour(255, 255, 255))

		self.sideNote = wx.Notebook(self.sidePanel, -1, style=wx.NB_RIGHT | wx.NB_MULTILINE)
		self.sideNote.SetBackgroundColour(wx.Colour(255, 255, 255))

		self.closePanel = wx.Panel(self.sideNote, -1, (0, 50), (45, 500), style=wx.NO_BORDER)

		self.compPanel = wx.Panel(self.sideNote, -1, (0, 50), (300, 500), style=wx.NO_BORDER)
		self.parent.compositePanel = frames.CompositePanel(self.parent, self.compPanel)
		self.compPanel.Hide()

		self.splicePanel = wx.Panel(self.sideNote, -1, (0, 50), (300, 500), style=wx.NO_BORDER)
		self.parent.splicePanel = frames.SplicePanel(self.parent, self.splicePanel)
		self.splicePanel.Hide()

		start_pos = 50
		if platform_name[0] == "Windows" :
			start_pos = 0

		self.eldPanel = wx.Panel(self.sideNote, -1, (0, start_pos), (300, 500), style=wx.NO_BORDER)
		self.eldPanel.SetBackgroundColour(wx.Colour(255, 255, 255))

		self.subSideNote = wx.Notebook(self.eldPanel, -1, style=wx.NB_TOP | wx.NB_MULTILINE)
		self.subSideNote.SetBackgroundColour(wx.Colour(255, 255, 255))

		self.manualPanel = wx.Panel(self.subSideNote, -1, (0, 50), (300, 500), style=wx.NO_BORDER)
		self.parent.eldPanel = frames.ELDPanel(self.parent, self.manualPanel)
		self.manualPanel.Hide()

		self.autoPanel = wx.Panel(self.subSideNote, -1, (0, 50), (300, 500), style=wx.NO_BORDER)
		self.parent.autoPanel = frames.AutoPanel(self.parent, self.autoPanel)
		self.autoPanel.Hide()

		self.subSideNote.AddPage(self.autoPanel, 'Auto Correlation')
		self.subSideNote.AddPage(self.manualPanel, 'Manual Correlation')
		self.subSideNote.SetSelection(0)
		self.subSideNote.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnSelectELDNote)

		self.filterPanel = wx.Panel(self.sideNote, -1, (0, 50), (300, 500), style=wx.NO_BORDER)
		self.parent.filterPanel = frames.FilterPanel(self.parent, self.filterPanel)
		self.filterPanel.Hide()

		self.optPanel = wx.Panel(self.sideNote, -1, (0, 50), (300, 500), style=wx.NO_BORDER)
		self.parent.optPanel = frames.PreferencesPanel(self.parent, self.optPanel)
		self.optPanel.Hide()

		#self.helpPanel = wx.Panel(self.sideNote, -1, (0, 50), (300, 500), style=wx.NO_BORDER )

		#self.logPanel = wx.Panel(self.sideNote, -1, (0, 50), (300, 500), style=wx.NO_BORDER)

		self.agePanel = wx.Panel(self.sideNote, -1, (0, 50), (300, 500), style=wx.NO_BORDER)
		self.parent.agePanel = frames.AgeDepthPanel(self.parent, self.agePanel)
		#self.agePanel.Enable(False)

		#help = "About Correlator ...\n "
		#self.helpText = wx.TextCtrl(self.helpPanel, -1, help, (0, 0), (300, 500), style=wx.TE_MULTILINE|wx.TE_READONLY|wx.VSCROLL|wx.TE_AUTO_URL|wx.TE_WORDWRAP)
		#self.helpText.SetEditable(False)

		#report = "Report ..."
		#self.reportText = wx.TextCtrl(self.logPanel, -1, report, (0, 0), (300, 500), style=wx.TE_MULTILINE | wx.SUNKEN_BORDER | wx.ALWAYS_SHOW_SB )
		#self.reportText.SetEditable(False)

		self.sideNote.AddPage(self.closePanel, 'Close')
		self.sideNote.AddPage(self.compPanel, 'Composite')
		self.sideNote.AddPage(self.splicePanel, 'Splice')
		self.sideNote.AddPage(self.eldPanel, 'Core-Log Integration')
		#self.sideNote.AddPage(self.eldPanel, 'Correlation')

		#self.sideNote.AddPage(self.autoPanel, 'Auto Correlation')
		self.sideNote.AddPage(self.agePanel, 'Age Depth Model')

		self.sideNote.AddPage(self.filterPanel, 'Filter')
		self.sideNote.AddPage(self.optPanel, 'Preferences')
		#self.sideNote.AddPage(self.logPanel, 'Report')

		#self.sideNote.AddPage(self.helpPanel, 'Help')
		self.sideNote.SetSelection(1)
		self.sideNote.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnSelectNote)

		wx.EVT_MOTION(self, self.OnMotion)
		wx.EVT_LEFT_DOWN(self, self.OnLMouse)
		wx.EVT_RIGHT_DOWN(self, self.OnRMouse)
		wx.EVT_LEFT_UP(self, self.OnMouseUp)
		wx.EVT_MOUSEWHEEL(self, self.OnMouseWheel)

		#wx.EVT_KEY_DOWN(self, self.OnChar)
		wx.EVT_KEY_DOWN(self, self.OnChar)
		wx.EVT_KEY_DOWN(self.sidePanel, self.OnChar)
		wx.EVT_KEY_UP(self, self.OnCharUp)
		wx.EVT_KEY_UP(self.sidePanel, self.OnCharUp)

	def OnInit(self):
		self.GuideCore = []
		self.Highlight_Tie = -1
		self.saganDepth = -1
		self.ShiftTieList = []
		self.minScrollRange = 0
		self.selectedHoleType = "" 
		self.selectedStartX = 0 
		self.selectedCount = 0
		self.SpliceTieFromFile = 0
		self.hole_sagan = -1 
		self.sagan_type = "" 
		self.LogTieList = []
		self.PreviewLog = [-1, -1, 1.0, 0, -1, -1, 1.0]
		self.showMenu = False
		self.splice_smooth_flag = 0
		self.autocoreNo = []
		self.HoleData = []
		self.SmoothData = []
		self.LogData = []
		self.LogSMData = []
		self.LogselectedTie = -1
		self.LDselectedTie = -1
		self.LogTieData = [] 
		self.SpliceData = []
		self.SpliceSmoothData = []
		self.LogSpliceData = []
		self.LogSpliceSmoothData = []
		self.firstPntAge = 0.0
		self.firstPntDepth = 0.0
		self.isLogMode = 0 
		self.StratData = []
		self.noOfHoles = 0
		self.logTie = -1
		self.SpliceTieData = []
		self.RealSpliceTie = []
		self.TieData = []
		self.SpliceCore = []
		self.UserdefStratData = []
		self.AdjustDepthCore = []
		self.spliceCount = 0
		self.begin_append = False 
		self.CurrentSpliceCore = -1
		self.PreviousSpliceCore = -1
		self.selectedCore = -1
		self.LogselectedCore = -1
		self.selectedTie = -1
		self.selectedLastTie = -1
		self.guideCore = -1
		self.guideSPCore = -1
		self.selectedType = "" 
		self.multipleType = False 
		self.activeTie = -1 
		self.activeSPTie = -1 
		self.activeSATie = -1 
		self.activeCore = -1 


	def OnInit_SPLICE(self):
		self.altType = self.selectedType
		self.SpliceData = []
		self.SpliceSmoothData = []
		self.SpliceTieData = []
		self.RealSpliceTie = []
		self.SpliceCore = []
		self.spliceCount = 0
		self.begin_append = False 
		self.CurrentSpliceCore = -1
		self.PreviousSpliceCore = -1
		self.selectedTie = -1
		self.selectedLastTie = -1
		self.guideSPCore = -1
		self.SpliceDiff = 2
		self.selectedType = "" 
		self.altMultipleType = self.multipleType
		self.multipleType = False 
		self.SPgrabCore = -1
		self.spliceTie = -1
		self.SpliceCoreId = -1
		self.SplicedHole = []
		self.SPGuideCore = []
		self.SPselectedTie = -1
		self.SPselectedLastTie = -1
		self.splice_smooth_flag = 0

	def UpdateRANGE(self, type, min, max):
		for r in self.range :
			if r[0] == type :
				coef = max - min
				newrange = type, min, max, coef, r[4], r[5]
				self.range.remove(r)
				self.range.append(newrange)
				break


	def UpdateSMOOTH(self, type, smooth):
		for r in self.range :
			if r[0] == type :
				newrange = type, r[1], r[2], r[3], smooth, r[5] 
				self.range.remove(r)
				self.range.append(newrange)
				break

		if self.hole_sagan != -1 and type == self.sagan_type :
			for r in self.range :
				if r[0] == "splice" :
					newrange = r[0], r[1], r[2], r[3], smooth, r[5] 
					self.range.remove(r)
					self.range.append(newrange)
					break

	def UpdateDATATYPE(self, type, continue_flag):
		for r in self.range :
			if r[0] == type :
				newrange = type, r[1], r[2], r[3], r[4], continue_flag 
				self.range.remove(r)
				self.range.append(newrange)
				break


	def GetMINMAX(self, type):
		for r in self.range :
			if r[0] == type :
				return (r[1], r[2])
		return None

	def GetRulerUnitsStr(self):
		return self.rulerUnits

	def GetRulerUnitsIndex(self):
		unitToIndexMap = {'m':0, 'cm':1, 'mm':2}
		return unitToIndexMap[self.rulerUnits]

	def GetRulerUnitsFactor(self):
		unitToFactorMap = {'m':1.0, 'cm':100.0, 'mm':1000.0}
		return unitToFactorMap[self.rulerUnits]

	def OnSelectELDNote(self, event):
		note_id = event.GetSelection()
		if self.prevNoteId == note_id :
			self.prevNoteId = -1
			return

		self.manualPanel.Hide()
		self.autoPanel.Hide()

		if note_id == 0 :
			self.mode = 3
			self.autoPanel.Show()
			self.parent.showSplicePanel = 0 
			self.parent.showCompositePanel = 0 
			self.parent.showELDPanel = 0 
		else :
			#if self.ShowAutoPanel == False :
			self.manualPanel.Show()
			self.parent.showELDPanel = 1
			self.mode = 3
			if self.spliceWindowOn == 0 : 
				self.parent.OnActivateWindow(1)
			self.parent.showSplicePanel = 0 
			self.parent.showCompositePanel = 0 
			self.parent.eldPanel.OnUpdate()
		self.prevNoteId = note_id
		self.subSideNote.SetSelection(note_id)
		#event.Skip()

	def OnSelectNote(self, event):
		note_id = event.GetSelection()

		#self.closeFlag = False 
		#self.sideNote.SetSize((self.sideTabSize,self.Height))
		#self.sidePanel.SetSize((self.sideTabSize,self.Height))
		#x, y = self.GetClientSizeTuple()
		#self.SetSashPosition(x - self.sideTabSize, False)

		self.compPanel.Hide()
		self.splicePanel.Hide()
		self.eldPanel.Hide()
		self.filterPanel.Hide()
		self.agePanel.Hide()
		#self.autoPanel.Hide()
		self.optPanel.Hide()
		#self.logPanel.Hide()
		#self.helpPanel.Hide()

		if note_id == 0 :
			if self.CLOSEFLAG == 0 :
				self.parent.showCompositePanel = 0 
				self.parent.showSplicePanel = 0 
				self.parent.showELDPanel = 0 
				self.Width, self.Height = self.parent.GetClientSizeTuple()
				self.Width = self.Width - 45 
				self.sideNote.SetSize((45, self.Height))
				self.sidePanel.SetPosition((self.Width, 0))
				self.sidePanel.SetSize((45, self.Height))
				self.UpdateDrawing()
				self.CLOSEFLAG = 1
				self._Buffer = wx.EmptyBitmap(self.Width, self.Height)
				if self.spliceWindowOn == 0 :
					self.splicerX = self.Width + 45
				self.UpdateDrawing()
		else :
			if self.CLOSEFLAG == 1 :
				self.Width, self.Height = self.parent.GetClientSizeTuple()
				self.Width = self.Width - self.sideTabSize
				self.sidePanel.SetPosition((self.Width, 0))
				self.sidePanel.SetSize((self.sideTabSize, self.Height))
				self.sideNote.SetSize((self.sideTabSize, self.Height))
				self.CLOSEFLAG = 0 
				self._Buffer = wx.EmptyBitmap(self.Width, self.Height)
				if self.spliceWindowOn == 0 :
					self.splicerX = self.Width + 45
				self.UpdateDrawing()

		if note_id == 1 :
			self.compPanel.Show()
			self.parent.showCompositePanel = 1
			self.mode = 1
			#if self.spliceWindowOn == 1 : 
			#	self.parent.OnActivateWindow(1)
			self.parent.showSplicePanel = 0 
			self.parent.showELDPanel = 0 
			self.parent.compositePanel.OnUpdate()
		elif note_id == 2 :
			self.splicePanel.Show()
			self.parent.showSplicePanel = 1
			self.mode = 2
			if self.spliceWindowOn == 0 : 
				self.parent.OnActivateWindow(1)
			self.parent.showCompositePanel = 0 
			self.parent.showELDPanel = 0 
			self.parent.splicePanel.OnUpdate()
		elif note_id == 3 :
			self.mode = 3
			#if self.ShowAutoPanel == False :
			self.eldPanel.Show()
			self.parent.showELDPanel = 1
			self.mode = 3
			if self.spliceWindowOn == 0 : 
				self.parent.OnActivateWindow(1)
			self.parent.showSplicePanel = 0 
			self.parent.showCompositePanel = 0 

			if self.parent.showELDPanel == 1 :
				self.parent.eldPanel.OnUpdate()

			# -------- HJ
			#self.mode = 3
			#self.autoPanel.Show()
			#self.parent.showSplicePanel = 0 
			#self.parent.showCompositePanel = 0 
			#self.parent.showELDPanel = 0 
			# --------
		elif note_id == 4 :
			self.mode = 4
			self.agePanel.Show()
			self.parent.showSplicePanel = 0 
			self.parent.showCompositePanel = 0 
			self.parent.showELDPanel = 0 
		elif note_id == 5 :
			self.filterPanel.Show()
			self.parent.showSplicePanel = 0 
			self.parent.showCompositePanel = 0 
			self.parent.showELDPanel = 0 
		elif note_id == 6 :
			self.optPanel.Show()
			#self.parent.optPanel.updateItem()
			self.parent.showSplicePanel = 0 
			self.parent.showCompositePanel = 0 
			self.parent.showELDPanel = 0 
		#elif note_id == 7 :
		#	self.logPanel.Show()
		#	self.parent.showReportPanel = 1
		#	self.parent.OnUpdateReport()
		#	self.parent.showSplicePanel = 0 
		#	self.parent.showCompositePanel = 0 
		#	self.parent.showELDPanel = 0 
		#elif note_id == 9 :
		#	self.helpPanel.Show()
		#	self.parent.OnUpdateHelp()
		#	self.parent.showCompositePanel = 0 
		#	self.parent.showSplicePanel = 0 
		#	self.parent.showELDPanel = 0 
		#	self.parent.showReportPanel = 0 

		#if self.note_id == 0 and note_id != 0 :
		#	self.closeFlag = True

		#self.note_id = note_id
		event.Skip()

	def DrawAgeModelRuler(self, dc):
		dc.SetBrush(wx.TRANSPARENT_BRUSH)
		dc.SetPen(wx.Pen(self.colorDict['foreground'], 1))
		dc.SetTextBackground(self.colorDict['background'])
		dc.SetTextForeground(self.colorDict['foreground'])
		dc.SetFont(self.font2)

		self.rulerHeight = self.Height - self.startAgeDepth

		# Draw ruler on age model space
		depth = self.startAgeDepth 
		pos = self.rulerStartAgeDepth 
		dc.DrawLines(((self.compositeX, 0), (self.compositeX, self.Height)))

		rulerUnitsStr = " (" + self.GetRulerUnitsStr() + ")"
		dc.DrawText("Depth", self.compositeX - 35, self.startAgeDepth - 45)
		dc.DrawText(rulerUnitsStr, self.compositeX - 35, self.startAgeDepth - 35)
		
		# Draw depth scale ticks
		rulerRange = (self.rulerHeight / (self.ageYLength / self.ageGap))
		self.ageRulerTickRate = self.CalcTickRate(rulerRange)

		unitAdjFactor = self.GetRulerUnitsFactor()
		while True :
			adjPos = pos * unitAdjFactor
			dc.DrawLines(((self.compositeX - 10, depth), (self.compositeX, depth)))
			wid, hit = dc.GetTextExtent(str(adjPos))
			dc.DrawRotatedText(str(adjPos), self.compositeX - 5 - hit * 2, depth + wid/2, 90.0)
			depth = depth + (self.ageRulerTickRate * self.ageYLength / self.ageGap)
			dc.DrawLines(((self.compositeX - 5, depth), (self.compositeX, depth)))
			depth = depth + (self.ageRulerTickRate * self.ageYLength / self.ageGap) 
			pos = pos + self.ageRulerTickRate * 2
			if depth > self.Height :
				break

		self.rulerEndAgeDepth = pos
		dc.DrawLines(((self.compositeX, self.startAgeDepth), (self.splicerX - 50, self.startAgeDepth)))
		dc.DrawText("Age(Ma)", self.compositeX + 5, self.startAgeDepth - 45)
		y1 = self.startDepth - 7
		y2 = self.startDepth
		y3 = self.startDepth - 20 
		pos = 1.0 
		#width = ((0.5 - self.minAgeRange) * self.ageLength) 
		x = self.compositeX + ((pos - self.minAgeRange) * self.ageLength)
		#x = self.compositeX + width 

		maxsize = self.splicerX - 50
		for i in range(self.maxAgeRange) :
			if x > self.compositeX and x < maxsize :
				dc.DrawLines(((x, y1), (x, y2)))
				dc.DrawText(str(pos), x - 10, y3)
			pos = pos + self.ageXGap;
			x = self.compositeX + ((pos - self.minAgeRange) * self.ageLength)

		# Draw ruler on splicer space
		if self.spliceWindowOn == 1 :
			depth = self.startDepth 
			pos = self.SPrulerStartDepth 

			dc.DrawLines(((self.splicerX, 0), (self.splicerX, self.Height)))

			self.SPrulerHeight = self.Height - self.startDepth

			temppos = self.SPrulerStartDepth % (self.gap / 2)
			dc.DrawLines(((self.splicerX - 10, depth), (self.splicerX, depth)))
			if temppos > 0 : 
				dc.DrawText(str(pos), self.splicerX - 35, depth - 5)
				depth = depth + (self.length / 2) * (1 - temppos) 
				dc.DrawLines(((self.splicerX - 5, depth), (self.splicerX, depth)))
				depth = depth + self.length / 2 
				pos = pos - temppos + self.gap

			dc.DrawText("Ma", self.splicerX - 35, 20)
			agedepth = 0.0 
			if self.SPrulerStartAgeDepth <= 0.0 :
				dc.DrawText(str(agedepth), self.splicerX - 35, self.startAgeDepth - 5)
			count = 1
			agedepth = self.AgeUnit
			agey = count * self.AgeSpliceGap
			if self.spliceYLength > 40 :
				while True :
					y = self.startAgeDepth + (agey - self.SPrulerStartAgeDepth) * (self.spliceYLength / self.gap)
					dc.DrawLines(((self.splicerX - 10, y), (self.splicerX, y)))
					dc.DrawText(str(agedepth), self.splicerX - 35, y - 5)
					if y > self.Height : 
						break
					count = count + 1
					agedepth = count * self.AgeUnit
					agey = count * self.AgeSpliceGap
			elif self.spliceYLength > 20 :
				while True :
					y = self.startAgeDepth + (agey - self.SPrulerStartAgeDepth) * (self.spliceYLength / self.gap)
					if count % 2 == 0 :
						dc.DrawLines(((self.splicerX - 10, y), (self.splicerX, y)))
						dc.DrawText(str(agedepth), self.splicerX - 35, y - 5)
					else :
						dc.DrawLines(((self.splicerX - 5, y), (self.splicerX, y)))

					if y > self.Height : 
						break
					count = count + 1
					agedepth = count * self.AgeUnit
					agey = count * self.AgeSpliceGap
			else :
				while True :
					y = self.startAgeDepth + (agey - self.SPrulerStartAgeDepth) * (self.spliceYLength / self.gap)
					if count % 5 == 0 :
						dc.DrawLines(((self.splicerX - 10, y), (self.splicerX, y)))
						dc.DrawText(str(agedepth), self.splicerX - 35, y - 5)
					else :
						dc.DrawLines(((self.splicerX - 5, y), (self.splicerX, y)))

					if y > self.Height : 
						break
					count = count + 1
					agedepth = count * self.AgeUnit
					agey = count * self.AgeSpliceGap

			depth = self.startAgeDepth - 20
			dc.DrawLines(((self.splicerX, depth), (self.Width, depth)))


	# Given rulerRange (in meters), return a suitable rate of depth scale tick marks (in meters).
	def CalcTickRate(self, rulerRange):
		result = 1.0
		exp = 5;
		while True:
			bigTens = pow(10, exp)
			halfBigTens = bigTens / 2.0
			smallTens = pow(10, exp - 1)
			if rulerRange <= pow(10, exp) and rulerRange > pow(10, exp - 1):
				# found the proper range, now determine which of 10^exp, (10^exp)/2, 10^(exp-1)
				# it's nearest. That number/10 will be our tick rate.
				diffList = [ bigTens - rulerRange, rulerRange - smallTens, abs(bigTens / 2.0 - rulerRange) ]
				result = min(diffList)
				resultIndex = diffList.index(result)
				if resultIndex == 0:
					result = bigTens / 10.0
				elif resultIndex == 1:
					result = smallTens / 10.0
				elif resultIndex == 2:
					result = halfBigTens / 10.0
				break
			exp = exp - 1
		
		return result

	def DrawRuler(self, dc):
		dc.SetBrush(wx.TRANSPARENT_BRUSH)
		dc.SetPen(wx.Pen(self.colorDict['foreground'], 1))
		dc.SetTextBackground(self.colorDict['background'])
		dc.SetTextForeground(self.colorDict['foreground'])
		dc.SetFont(self.font2)

		rulerUnitsStr = " (" + self.GetRulerUnitsStr() + ")"
		if self.timeseries_flag == False :
			dc.DrawText("Depth", self.compositeX - 35, self.startDepth - 45)
			dc.DrawText(rulerUnitsStr, self.compositeX - 35, self.startDepth - 35)
		else :
			dc.DrawText("Age", self.compositeX - 35, self.startDepth - 45)
			dc.DrawText("(Ma)", self.compositeX - 35, self.startDepth - 35)

		# Draw ruler on composite space
		depth = self.startDepth # depth in pixels
		pos = self.rulerStartDepth # depth in meters for tick labels
		dc.DrawLines(((self.compositeX, 0), (self.compositeX, self.Height))) # depth axis

		# Draw depth scale ticks
		self.rulerHeight = self.Height - self.startDepth
		rulerRange = (self.rulerHeight / self.length) * 2;
		self.rulerTickRate = self.CalcTickRate(rulerRange)

		unitAdjFactor = self.GetRulerUnitsFactor()
		while True :
			adjPos = pos * unitAdjFactor

			dc.DrawLines(((self.compositeX - 10, depth), (self.compositeX, depth))) # depth-labeled ticks
			wid, hit = dc.GetTextExtent(str(adjPos))
			dc.DrawRotatedText(str(adjPos), self.compositeX - 5 - hit * 2, depth + wid/2, 90.0)
			depth = depth + (self.rulerTickRate * self.length) / 2

			dc.DrawLines(((self.compositeX - 5, depth), (self.compositeX, depth))) # unlabeled ticks
			depth = depth + (self.rulerTickRate * self.length) / 2 

			pos = pos + self.rulerTickRate * 2
			if depth > self.Height :
				break

		self.rulerEndDepth = pos + 2.0

		# Draw ruler on splicer space
		if self.spliceWindowOn == 1 :
			depth = self.startDepth 
			pos = self.SPrulerStartDepth 

			if self.timeseries_flag == False :
				dc.DrawText("Depth", self.splicerX - 35, self.startDepth - 45)
				dc.DrawText(rulerUnitsStr, self.splicerX - 35, self.startDepth - 35)
			else :
				dc.DrawText("Age", self.splicerX - 35, self.startDepth - 45)
				dc.DrawText("(Ma)", self.splicerX - 35, self.startDepth - 35)

			dc.DrawLines(((self.splicerX, 0), (self.splicerX, self.Height))) # depth axis
			self.SPrulerHeight = self.Height - self.startDepth
			
			while True :
				adjPos = pos * unitAdjFactor
				dc.DrawLines(((self.splicerX - 10, depth), (self.splicerX, depth)))
				wid, hit = dc.GetTextExtent(str(adjPos))
				dc.DrawRotatedText(str(adjPos), self.splicerX - 5 - hit * 2, depth + wid/2, 90.0)
				depth = depth + (self.rulerTickRate * self.length) / 2
				dc.DrawLines(((self.splicerX - 5, depth), (self.splicerX, depth)))
				depth = depth + (self.rulerTickRate * self.length) / 2 
				pos = pos + self.rulerTickRate * 2
				if depth > self.Height :
					break

			self.SPrulerEndDepth = pos + 2.0 
			depth = self.startDepth - 20
			dc.DrawLines(((self.splicerX, depth), (self.Width, depth)))

		depth = self.startDepth - 20
		if self.spliceWindowOn == 1 :
			dc.DrawLines(((self.compositeX, depth), (self.splicerX - 50, depth)))
		else :
			dc.DrawLines(((self.compositeX, depth), (self.Width, depth)))


	def DrawHoleGraph(self, dc, hole, smoothed, prev_type):
		dc.SetBrush(wx.TRANSPARENT_BRUSH)
		dc.SetPen(wx.Pen(self.colorDict['foreground'], 1))
		dc.SetTextBackground(self.colorDict['background'])
		dc.SetTextForeground(self.colorDict['foreground'])
		dc.SetFont(self.font2)

		startX = 0 
		if self.Done == False :
			if len(self.WidthsControl) == 0 :
				startX = self.compositeX - self.minScrollRange + 50
				self.WidthsControl.append(startX)
				self.WidthsControl.append(startX + self.holeWidth + 50)
			else :
				startX = self.WidthsControl[self.HoleCount] 
				self.WidthsControl.append(startX + self.holeWidth + 50)
		else :
			if self.HoleCount < 0 :
				startX = self.WidthsControl[0] 
			else : 
				startX = self.WidthsControl[self.HoleCount] 

		rangeMax = startX + self.holeWidth

		if self.showHoleGrid == True :
			if startX < self.splicerX :
				dc.SetPen(wx.Pen(self.colorDict['foreground'], 1, style=wx.DOT))
				dc.DrawLines(((startX, self.startDepth - 20), (startX, self.Height)))
			if smoothed >= 5 :
				dc.SetPen(wx.Pen(self.colorDict['foreground'], 1, style=wx.DOT))
				rangeMax = self.splicerX + (self.holeWidth * 2) + 150
				dc.DrawLines(((rangeMax, self.startDepth - 20), (rangeMax, self.Height)))

		holeInfo = hole[0]
		forcount = holeInfo[8] 

		type = holeInfo[2]
		if type == "Natural Gamma" :
			type = "NaturalGamma"

		if smoothed == 5 or smoothed == 6 or smoothed == 7:
			type = 'log'
			
		overlapped_flag = False
		if self.pressedkeyD == 1 :
			if self.selectedHoleType == holeInfo[2] :
				if prev_type != type :
					self.selectedStartX = startX 
					self.selectedCount = 0 
				else :
					overlapped_flag = True 
					self.selectedCount += 1 

					dc.SetBrush(wx.Brush(self.overlapcolorList[self.selectedCount]))
					dc.SetPen(wx.Pen(self.overlapcolorList[self.selectedCount], 1))
					dc.DrawRectangle(startX, self.startDepth - 20, 30, 20)
					dc.SetBrush(wx.TRANSPARENT_BRUSH)

		smooth_id = -1
		for r in self.range :
			if r[0] == type : 
				self.minRange = r[1]
				self.maxRange = r[2]
				if r[3] != 0.0 :
					self.coefRange = self.holeWidth / r[3]
				else :
					self.coefRange = 0 
				smooth_id = r[4]
				self.continue_flag = r[5] 
				break

		if smoothed == 0 :
			if smooth_id == 1 :
				self.coreCount = self.coreCount + forcount 
				return type 
		elif smoothed == 3 :
			if smooth_id == 1 :
				smoothed = 0
			elif smooth_id <= 0 :
				self.coreCount = self.coreCount + forcount 
				return type 

		compositeflag = 1
		if smoothed != 2 and smoothed < 5 and self.splicerX < rangeMax:
			compositeflag = 0

		rangeMax = startX
		spliceflag = 0 
		drawSplicerflag = 0

		len_hole = len(hole) - 1
		if len_hole == 0 :
			return type 

		if self.LogClue == True and self.LogTieList != [] and ((rangeMax + self.holeWidth) < self.splicerX) :
			if self.HoleCount >= 0 :
				logtie_data = self.LogTieList[self.HoleCount] 
				points_list = logtie_data[1]
				depth1 = 0
				depth2 = 0
				i = 0
				for point in points_list : 
					if i == 0 : 
						depth1 = point
						i = 1
					else : 
						depth2 = point
						dc.SetPen(wx.Pen(self.colorDict['mbsf'], 1))
						y2 = self.startDepth + (depth2 - self.rulerStartDepth) * (self.length / self.gap)
						dc.DrawLines(((rangeMax, y2), (rangeMax + 15, y2)))
						i = 0 


		affine = 0.0
		#for i in range(forcount) :
		for i in range(len_hole) : 
			holedata = hole[i + 1] # actually coredata

			if self.CurrentSpliceCore == self.coreCount :
				spliceflag = 1	
				drawSplicerflag = 1 

			for autoHole in self.autocoreNo : 
				if autoHole == self.HoleCount :
					spliceflag = 2	
					break
				elif self.parent.autoPanel.ApplyFlag == 1 :
					spliceflag = 2	

			affine = self.DrawCoreGraph(dc, self.coreCount, startX, holeInfo, holedata, smoothed, spliceflag, compositeflag, affine) 

			if overlapped_flag == True :
				self.DrawCoreGraph(dc, self.coreCount, self.selectedStartX, holeInfo, holedata, -1, 0, 1, 0.0) 

			spliceflag = 0 
			coreData = holedata[10]
			depthmin, temp = coreData[0]
			datamax = len(coreData) - 1
			depthmax, temp = coreData[datamax]

			l = []
			if smoothed == 0 or smoothed == 5 or smoothed == 6: 
				# index, leg, site, hole, core, min data, max data 
				l = []
				l.append((self.coreCount, holeInfo[0], holeInfo[1], holeInfo[7], holedata[0], holedata[3], holedata[4], depthmin, depthmax, holedata[6], holeInfo[2], holedata[8], self.HoleCount))
				self.DrawData["CoreInfo"].append(l)

			self.coreCount = self.coreCount + 1

		# DRAWING TITLE
		dc.SetPen(wx.Pen(self.colorDict['foreground'], 1))
		if compositeflag == 1 and smoothed == 0 :
			dc.DrawText("Leg: " + holeInfo[1] + " Site: " + holeInfo[0] + " Hole: " + holeInfo[7], rangeMax, 5) 
			dc.DrawText(holeInfo[2] + ", Range: " + str(holeInfo[5]) + ":" + str(holeInfo[6]), rangeMax, 25)
		if smoothed == 1 :
			dc.DrawText("Leg: " + holeInfo[1] + " Site: " + holeInfo[0] + " Hole: " + holeInfo[7], rangeMax, 5) 
			dc.DrawText(holeInfo[2] + ", Range: " + str(holeInfo[5]) + ":" + str(holeInfo[6]), rangeMax, 25)
		if smoothed >= 5 :
			title_pos = self.splicerX + (self.holeWidth * 2) + (50 * 2) + 50
			# rangeMax
			dc.DrawText("Leg: " + holeInfo[1] + " Site: " + holeInfo[0] + " Hole: " + holeInfo[7], title_pos, 5)
			dc.DrawText("Log, Range: " + str(holeInfo[5]) + ":" + str(holeInfo[6]), title_pos, 25)

		return type


	def GetCoreId(self, dc, hole, core):
		coreid = 0
		ret = 0
		for data in self.DrawData["CoreInfo"]:
			for r in data:
				if r[3] == hole and r[4] == str(core):
					coreid = int(r[0])
					ret = 1
				if ret == 1:
					break
			if ret == 1:
				break

		return coreid


	def DrawSplice(self, dc, hole, smoothed):
		dc.SetTextForeground(self.colorDict['foreground'])
		dc.SetFont(self.font2)
		self.FirstDepth = 999.99

		holeInfo = hole[0]
		forcount = holeInfo[8] 
		gap = (holeInfo[6] - holeInfo[5]) / 5 

		modifiedType = "splice"
		if smoothed == 7 :
			modifiedType = "altsplice"

		for r in self.range :
			if r[0] == modifiedType :
				self.minRange = r[1]
				self.maxRange = r[2]
				if r[3] != 0.0 :
					self.coefRangeSplice = self.holeWidth / r[3]
				else :
					self.coefRangeSplice = 0 
				self.smooth_id = r[4]
				break

		if smoothed != 6 : 
			self.smooth_id = -1 

		type = self.selectedType
		if self.multipleType == True :
			type = "Multiple data type"


		# draw graph tick marks
		# 0 : unsmoothed, 1 : smoothed, 2 : both
		if smoothed == 0 or smoothed == 1 :
			rangeMax = self.splicerX + 50
			if self.LogClue == True and self.LogTieList != [] :
				for logtie_data in self.LogTieList : 
					points_list = logtie_data[1]
					if logtie_data[0] == 0 :
						i = 0
						dc.SetPen(wx.Pen(self.colorDict['mbsf'], 1))
						for point in points_list : 
							if i == 0 : 
								depth = point
								y = self.startDepth + (depth - self.rulerStartDepth) * (self.length / self.gap)
								dc.DrawLines(((rangeMax, y), (rangeMax + 15, y)))
								i = 1
							else : 
								i = 0 

			dc.DrawText("Leg: " + holeInfo[1] + " Site: " + holeInfo[0] + " Hole: " + "Splice", rangeMax, 5) 
			dc.DrawText(type, rangeMax, 25)
			dc.SetPen(wx.Pen(self.colorDict['foreground'], 1, style=wx.DOT))
			dc.DrawLines(((rangeMax, self.startDepth - 20), (rangeMax, self.Height)))

		elif smoothed == 3 :
			rangeMax = self.splicerX + self.holeWidth + 100
			dc.DrawText("Leg: " + holeInfo[1] + " Site: " + holeInfo[0] + " Hole: " + "ELD", rangeMax, 5) 
			dc.DrawText(type, rangeMax, 25)
			dc.SetPen(wx.Pen(self.colorDict['foreground'], 1, style=wx.DOT))
			dc.DrawLines(((rangeMax, self.startDepth - 20), (rangeMax, self.Height)))
		elif smoothed == 7 :
			type = self.altType
			if self.altMultipleType == True :
				type = "Multiple data type"

			rangeMax = self.splicerX + self.holeWidth * 2 + 150
			dc.DrawText("Leg: " + holeInfo[1] + " Site: " + holeInfo[0] + " Hole: " + "Splice", rangeMax, 5) 
			dc.DrawText(type, rangeMax, 25)

			dc.SetPen(wx.Pen(self.colorDict['foreground'], 1, style=wx.DOT))
			dc.DrawLines(((rangeMax, self.startDepth - 20), (rangeMax, self.Height)))

			hole_core = holeInfo[7]
			len_hole = len(hole) - 1;	
			if len_hole == 0:
				return
			if self.MainViewMode == True :
				#for i in range(forcount) : 
				for i in range(len_hole) : 
					holedata = hole[i + 1]
					self.DrawSpliceCore(dc, -1, holedata, 7, hole_core + holedata[0])
			return
		
		len_hole = len(hole) - 1;	
		if len_hole == 0:
			return

		hole_core = holeInfo[7]
		index = 0 
		ret = 0
		#self.lastSpliceX = -999.99 
		splicesize = len(self.SpliceCore) 
		if self.MainViewMode == True :
			#for i in range(forcount) :
			for i in range(len_hole) : 
				holedata = hole[i + 1]
				if index < splicesize :
					self.DrawSpliceCore(dc, self.SpliceCore[index], holedata, smoothed, hole_core + holedata[0])
					index = index + 1 
		else :
			self.AgeOffset = 0.0
			self.prevDepth = 0.0
			#for i in range(forcount) :
			for i in range(len_hole) :                             
				holedata = hole[i + 1]
				if index < splicesize :
					ret = self.DrawAgeSpliceCore(dc, self.SpliceCore[index], holedata[10], smoothed, holedata[7])
					index = index + 1 
					if ret == False :
						break


	def SaveAge(self, file):
		splicesize = len(self.SpliceCore) 
		for data in self.SpliceData:
			for hole in data:
				holeInfo = hole[0]
				forcount = holeInfo[8] 
				index = 0
				for i in range(forcount) : 
					holedata = hole[i + 1]
					if index < splicesize :
						coreData = holedata[10]
						prevydepth = 0.0
						ba = 0.0

						for r in coreData :
							y, x = r
							depth = 0.0
							for rateItem in self.AgeYRates :
								ydepth, ba, bn = rateItem
								if y > prevydepth and y <= ydepth :
									depth = ydepth
									break
								prevydepth = ydepth
							if depth != 0.0 :
								y = (ba * y) / depth
								#self.prevDepth = depth
								y = int(100.0 * y) / 100.0;
							else :
								#y = (ba * y) / self.prevDepth
								y = 0.0

							file.write(str(y) + "\n")

						index = index + 1 


	def DrawAgeSpliceCore(self, dc, index, coreData, smoothed, annotation):
		dc.SetPen(wx.Pen(self.colorDict['splice'], 1))
		if smoothed == 2 :
			dc.SetPen(wx.Pen(self.colorDict['smooth'], 1))

		splicelines = []
		# draw nodes
		si = 0	
		sx = 0
		sy = 0
		spx = 0
		spy = 0
		prevydepth = self.firstPntDepth 
		prevAge = self.firstPntAge

		ba = 0.0

		startX = self.splicerX + 50
		if len(self.AgeYRates) > 0 :
			for r in coreData :
				y, x = r
				if y < self.firstPntDepth :
					continue

				depth = 0.0
				prevydepth = self.firstPntDepth 
				for rateItem in self.AgeYRates :
					ydepth, ba, bn = rateItem
					if y > prevydepth and y <= ydepth :
						depth = ydepth
						break
					prevydepth = ydepth
					prevAge = ba

				if depth != 0.0 :
					deltaAge = ba - prevAge 
					deltaDepth = ydepth - prevydepth 
					y = (deltaAge / deltaDepth) * (y - prevydepth) + prevAge
					y = (y / self.AgeUnit) * self.AgeSpliceGap

				sy = self.startAgeDepth + (y - self.SPrulerStartAgeDepth) * (self.spliceYLength / self.gap)
				x = x - self.minRange
				sx = (x * self.coefRangeSplice) + startX
				if si > 0 : 
					if self.prevDepth != depth :
						self.AgeOffset = spy - sy
					sy = sy + self.AgeOffset
					splicelines.append((spx, spy, sx, sy))
				else :
					si = si + 1 
					sy = sy + self.AgeOffset
					
				spx = sx
				spy = sy
				self.prevDepth = depth
		else :
			for r in coreData :
				y, x = r
				if y < self.firstPntDepth :
					continue
				y = y + self.AdjustAgeDepth
				sy = self.startAgeDepth + (y - self.SPrulerStartAgeDepth) * (self.spliceYLength / self.gap)
				x = x - self.minRange
				sx = (x * self.coefRangeSplice) + startX 
				if si > 0 : 
					splicelines.append((spx, spy, sx, sy))
				else :
					si = si + 1 
				spx = sx
				spy = sy

		x = 0
		y = 0
		for r in splicelines :
			px, py, x, y = r
			dc.DrawLines(((px, py), (x, y))) 

		if y > 0 and smoothed < 3 : 
			dc.SetPen(wx.Pen(self.colorDict['foreground'], 1))
			if len(annotation) > 0 :
				dc.DrawText(annotation, startX - 20, y - 20)
				dc.DrawLines(((startX - 20, y), (startX, y)))
			if self.isLogMode == 0 :
				dc.DrawLines(((x - 10, y), (x + 10, y))) 

		if y < self.Height :
			return True

		return False 


	def DrawSpliceCore(self, dc, index, holedata, smoothed, hole_core):
		coreData = holedata[10]
		annotation = holedata[7]
		if self.FirstDepth == 999.99 :
			if coreData != [] : 
				self.FirstDepth, x = coreData[0]

		dc.SetPen(wx.Pen(self.colorDict['splice'], 1))
		log_number = 0

		if smoothed == 2 :
			dc.SetPen(wx.Pen(self.colorDict['smooth'], 1))
		elif smoothed == 3 :
			dc.SetPen(wx.Pen(self.colorDict['log'], 1))
			log_number = 1 
		elif smoothed == 4 :
			dc.SetPen(wx.Pen(wx.Colour(0, 139, 0), 1))
			log_number = 2 
		elif smoothed == 5 :
			dc.SetPen(wx.Pen(wx.Colour(255, 184, 149), 1))
			log_number = 1 
		elif smoothed == 6 :
			dc.SetPen(wx.Pen(wx.Colour(255, 184, 149), 1))
			log_number = 2 
		elif smoothed == 7 :
			dc.SetPen(wx.Pen(wx.Colour(0, 139, 0), 1))
			log_number = 2 

		splicelines = []

		# draw nodes
		si = 0	
		sx = 0
		sy = 0
		spx = 0
		spy = 0
		x = 0
		y = 0

		min = 999.0
		max = -999.0

		startX = self.splicerX + (self.holeWidth * log_number) + 50 + (50 * log_number)
		if smoothed != 4 or self.saganDepth == -1:
			if smoothed != 4 :
				if self.smooth_id == 2 and self.saganDepth != -1  :
					return
				drawing_start = self.SPrulerStartDepth - 5.0

				for r in coreData :
					y, x = r
					if y >= drawing_start and y <= self.SPrulerEndDepth :
						sy = self.startDepth + (y - self.SPrulerStartDepth) * (self.length / self.gap)
						sx = x - self.minRange 
						sx = (sx * self.coefRangeSplice) + startX  
						if si > 0 : 
							splicelines.append((spx, spy, sx, sy, 0))
						if min > sx : 
							min = sx
						if max < sx : 
							max = sx
						spx = sx
						spy = sy
						si = si + 1 
			else :
				drawing_start = self.SPrulerStartDepth - 5.0

				for r in coreData :
					y, x = r
					if y >= drawing_start and y <= self.SPrulerEndDepth :
						if self.PreviewLog[0] == -1 :
							y = y + self.PreviewLog[3]
						elif y >= self.PreviewLog[0] and y <= self.PreviewLog[1] :
							#(m_eld - m_b) * m_rate + m_b;
							y = (y - self.PreviewLog[0]) * self.PreviewLog[2] + self.PreviewLog[0]		
							self.PreviewB = y
							self.PreviewOffset = y - r[0]
							self.PreviewBOffset = y - r[0]
						elif self.PreviewLog[4] == -1 and y > self.PreviewLog[1] :
							y = y + self.PreviewOffset
						elif self.PreviewLog[4] != -1 and y > self.PreviewLog[5] :
							y = y + self.PreviewOffset
						elif y >= self.PreviewLog[1] and y <= self.PreviewLog[5] :
							y = y + self.PreviewBOffset
							y = (y - self.PreviewB) * self.PreviewLog[6] + self.PreviewB		
							self.PreviewOffset = y - r[0]

						sy = self.startDepth + (y - self.SPrulerStartDepth) * (self.length / self.gap)
						sx = x - self.minRange 
						sx = (sx * self.coefRangeSplice) + startX
						if si > 0 : 
							splicelines.append((spx, spy, sx, sy, 0))
						if min > sx : 
							min = sx
						if max < sx : 
							max = sx
						spx = sx
						spy = sy 
						si = si + 1 

			x = 0
			y = 0

			#if len(splicelines) > 0 and self.DiscretePlotMode == 0 : 
			#	if self.lastSpliceX != -999.99 :
			#		for r in splicelines :
			#			px, py, x, y, f = r
			#			dc.DrawLines(((self.lastSpliceX, self.lastSpliceY), (px, py))) 
			#			break
			#	self.lastSpliceX = spx 
			#	self.lastSpliceY = spy 

			if self.DiscretePlotMode == 0 :
				for r in splicelines :
					px, py, x, y, f = r
					dc.DrawLines(((px, py), (x, y))) 
			else :
				for r in splicelines :
					px, py, x, y, f = r
					dc.DrawCircle(px, py, self.DiscretetSize)
		else : 
			lead = self.saganDepth - self.parent.winLength
			lag = self.saganDepth + self.parent.winLength

			drawing_start = self.SPrulerStartDepth - 5.0
			for r in coreData :
				y, x = r
				if y >= drawing_start and y <= self.SPrulerEndDepth :
					f = 0
					if y >= lead and y <= lag :
						f = 1
					if self.PreviewLog[0] == -1 :
						y = y + self.PreviewLog[3]
					elif y >= self.PreviewLog[0] and y <= self.PreviewLog[1] :
						#(m_eld - m_b) * m_rate + m_b;
						y = (y - self.PreviewLog[0]) * self.PreviewLog[2] + self.PreviewLog[0]		
						self.PreviewB = y
						self.PreviewOffset = y - r[0]
						self.PreviewBOffset = y - r[0]
					elif self.PreviewLog[4] == -1 and y > self.PreviewLog[1] :
						y = y + self.PreviewOffset
					elif self.PreviewLog[4] != -1 and y > self.PreviewLog[5] :
						y = y + self.PreviewOffset
					elif y >= self.PreviewLog[1] and y <= self.PreviewLog[5] :
						y = y + self.PreviewBOffset
						y = (y - self.PreviewB) * self.PreviewLog[6] + self.PreviewB		
						self.PreviewOffset = y - r[0]

					sy = self.startDepth + (y - self.SPrulerStartDepth) * (self.length / self.gap)
					sx = x - self.minRange 
					sx = (sx * self.coefRangeSplice) + startX
					if si > 0 : 
						splicelines.append((spx, spy, sx, sy, f))
					if min > sx : 
						min = sx
					if max < sx : 
						max = sx
					spx = sx
					spy = sy 
					si = si + 1 

			x = 0
			y = 0

			#if len(splicelines) > 0 and self.DiscretePlotMode == 0 : 
			#	if self.lastSpliceX != -999.99 :
			#		for r in splicelines :
			#			px, py, x, y, f = r
			#			if f == 1 :
			#				dc.SetPen(wx.Pen(wx.Colour(0, 191, 255), 1))
			#			else :
			#				#dc.SetPen(wx.Pen(self.colorDict['mudlineAdjust'], 1))
			#				dc.SetPen(wx.Pen(wx.Colour(255, 184, 149), 1))
			#			dc.DrawLines(((self.lastSpliceX, self.lastSpliceY), (px, py))) 
			#			break
			#	self.lastSpliceX = spx 
			#	self.lastSpliceY = spy 

			if self.DiscretePlotMode == 0 :
				for r in splicelines :
					px, py, x, y, f = r
					if f == 1 :
						dc.SetPen(wx.Pen(wx.Colour(0, 191, 255), 1))
					else :
						#dc.SetPen(wx.Pen(self.colorDict['mudlineAdjust'], 1))
						dc.SetPen(wx.Pen(wx.Colour(255, 184, 149), 1))
					dc.DrawLines(((px, py), (x, y))) 
			else :
				for r in splicelines :
					px, py, x, y, f = r
					if f == 1 :
						dc.SetPen(wx.Pen(wx.Colour(0, 191, 255), 1))
					else :
						#dc.SetPen(wx.Pen(self.colorDict['mudlineAdjust'], 1))
						dc.SetPen(wx.Pen(wx.Colour(255, 184, 149), 1))
					dc.DrawCircle(px, py, self.DiscretetSize)			

		hole = '-'
		core = -1
		ret = 0 
		for s in self.DrawData["CoreInfo"]:
			data = s
			for r in data:
				if r[0] == index :
					hole = r[3]
					core = r[4]
					ret = 1 
					break
			if ret == 1 :
				break

		if y > 0 and smoothed < 3 : 
			#dc.DrawText(str(hole)+str(core), self.splicerX + 10, y-5)
			dc.SetPen(wx.Pen(self.colorDict['foreground'], 1))
			if len(annotation) > 0 :
				dc.DrawText(annotation, startX - 20, y - 20)
				dc.DrawLines(((startX - 20, y), (startX, y)))
			else :
				dc.DrawText(hole_core, startX - 20, y - 20)
				dc.DrawLines(((startX - 20, y), (startX, y)))
			if self.isLogMode == 0 :
				dc.DrawLines(((x - 10, y), (x + 10, y))) 
		elif y > 0 and smoothed == 3:
			if len(annotation) > 0 :
				dc.DrawText(annotation, startX - 20, y - 20)
				dc.SetPen(wx.Pen(self.colorDict['foreground'], 1))
				dc.DrawLines(((startX - 20, y), (startX, y)))
			else :
				dc.DrawText(hole_core, startX - 20, y - 20)
				dc.SetPen(wx.Pen(self.colorDict['foreground'], 1))
				dc.DrawLines(((startX - 20, y), (startX, y)))
		elif y > 0 and smoothed == 7 :
			dc.SetPen(wx.Pen(self.colorDict['foreground'], 1))
			if len(annotation) > 0 :
				dc.DrawText(annotation, startX - 20, y - 20)
				dc.DrawLines(((startX - 20, y), (startX, y)))
				dc.DrawLines(((x - 10, y), (x + 10, y))) 
			else :
				dc.DrawText(hole_core, startX - 20, y - 20)
				dc.DrawLines(((startX - 20, y), (startX, y)))
				dc.DrawLines(((x - 10, y), (x + 10, y))) 

		if smoothed < 3 : 
			for r in splicelines :
				l = []
				#l.append( (index, startX, r[1], self.holeWidth+40, y-r[1]) )
				l.append((index, min, r[1], max - min, y - r[1], startX, self.holeWidth + 40))
				self.DrawData["SpliceArea"].append(l)
				break
		elif smoothed == 3 :
			for r in splicelines :
				l = []
				#l.append( (index, startX, r[1], self.holeWidth+40, y-r[1]) )
				l.append((index, min, r[1], max - min, y - r[1], startX, self.holeWidth + 40))
				self.DrawData["LogArea"].append(l)
				break
		splicelines = [] 


	def DrawStratCore(self, dc, spliceflag):
		startdepth = self.rulerStartDepth
		enddepth = self.rulerEndDepth 
		if spliceflag == True :
			startdepth = self.SPrulerStartDepth
			enddepth = self.SPrulerEndDepth 

		splice_x = self.holeWidth * 0.5 
		if spliceflag == True :
			splice_x = self.spliceHoleWidth * 0.75 
		for data in self.StratData:
			for r in data:
				order, hole, name, label, start, stop, rawstart, rawstop, age, type = r
				flag = 0
				if stop >= startdepth and start < startdepth :
					start = startdepth 
					flag = 1

				if start >= startdepth and start <= enddepth :
					if type == 0 :	#DIATOMS 
						dc.SetPen(wx.Pen(self.colorDict['diatom'], 1))
					elif type == 1 : #RADIOLARIA 
						dc.SetPen(wx.Pen(self.colorDict['rad'], 1))
					elif type == 2 : #FORAMINIFERA 
						dc.SetPen(wx.Pen(self.colorDict['foram'], 1))
					elif type == 3 : #NANNOFOSSILS 
						dc.SetPen(wx.Pen(self.colorDict['nano'], 1))
					elif type == 4 : #PALEOMAG 
						dc.SetPen(wx.Pen(self.colorDict['paleomag'], 1))

					start = self.startDepth + (start - startdepth) * (self.length / self.gap)
					stop = self.startDepth + (stop - startdepth) * (self.length / self.gap)
					#middle = start + (stop -start) / 2.0

					if spliceflag == True :
						#x = self.splicerX + splice_x 
						#x = x + 20 
						x = self.splicerX + 50 - 22
						dc.DrawText(label, x, start)
						x = x + 22 
						if flag == 0 :
							dc.DrawLines(((x - 5, start), (x + 5, start))) 
						dc.DrawLines(((x, start), (x, stop))) 
						dc.DrawLines(((x - 5, stop), (x + 5, stop))) 
					else :
						#x = self.WidthsControl[hole] + splice_x
						x = self.WidthsControl[hole] - 22 
						if self.splicerX > (x + 70) :
							dc.DrawText(label, x, start)
							x = x + 22 
							if flag == 0 :
								dc.DrawLines(((x - 5, start), (x + 5, start))) 
							dc.DrawLines(((x, start), (x, stop))) 
							dc.DrawLines(((x - 5, stop), (x + 5, stop))) 


	def DrawCoreGraph(self, dc, index, startX, holeInfo, holedata, smoothed, spliceflag, compositeflag, prev_affine):

		hole = holeInfo[7]
		coreno = holedata[0]
		min = holedata[3]
		max = holedata[4]
		affine = holedata[5]
		coreData = holedata[10] 
		annotation = holedata[7] 
		squish = holedata[6]
		quality = holedata[8] 
		sections = holedata[9]

		if spliceflag == 1 :
			spliceholewidth = self.splicerX + self.holeWidth + 100
			dc.SetPen(wx.Pen(self.colorDict['foreground'], 1, style=wx.DOT))
			dc.DrawLines(((spliceholewidth, self.startDepth - 20), (spliceholewidth, self.Height)))

		drawing_start = self.rulerStartDepth - 5.0
		if spliceflag == 1 :
			drawing_start = self.SPrulerStartDepth - 5.0
		elif compositeflag == 1 and smoothed == 2 : 
			drawing_start = self.SPrulerStartDepth - 5.0

		if self.pressedkeyS == 1 :
			if compositeflag == 1 and smoothed != 2 :
				dc.SetPen(wx.Pen(self.colorDict['foreground'], 1, style=wx.DOT))
				for y in sections :
					if y >= drawing_start and y <= self.rulerEndDepth :
						y = self.startDepth + (y - self.rulerStartDepth) * (self.length / self.gap)
						dc.DrawLines(((startX, y), (startX + self.holeWidth, y))) 


		if smoothed != -1 and affine != 0 :
			draw_flag = False
			depth_tie = -999
			data_tie = -999

			if self.ShiftClue == True :
				if startX < self.splicerX :
					coreno = int(coreno)
					for shifttie_data in self.ShiftTieList :
						if shifttie_data[1] == hole : 
							points_list = shifttie_data[2]
							i = 0
							for point in points_list : 
								if i == 0 : 
									if point == coreno :
										draw_flag = True 
									else :
										if draw_flag == True :
											break
								elif i == 1 : 
									if draw_flag == True  :
										depth_tie = point
								else :
									if draw_flag == True  :
										if self.HoleCount == shifttie_data[0] :
											data_tie = point
									i = -1
								i += 1
					if draw_flag == False :
						if affine != prev_affine :
							draw_flag = True 

			if smoothed == 6 :
				if self.LogClue == True :
					startX = self.splicerX + (self.holeWidth * 2) + 150
					draw_flag = True 

			if draw_flag == True :
				y_depth, x = coreData[0]
				if depth_tie != -999 :
					y_depth = depth_tie

				if y_depth >= drawing_start and y_depth <= self.rulerEndDepth :

					dc.SetPen(wx.Pen(self.colorDict['mbsf'], 1))
					y1 = self.startDepth + (y_depth - affine - self.rulerStartDepth) * (self.length / self.gap)
					dc.DrawLines(((startX - 5, y1), (startX + 5, y1))) 
					y = self.startDepth + (y_depth - self.rulerStartDepth) * (self.length / self.gap)
					dc.DrawLines(((startX - 5, y), (startX + 5, y))) 

					dc.SetPen(wx.Pen(self.colorDict['foreground'], 1))
					y = self.startDepth + (y_depth - self.rulerStartDepth) * (self.length / self.gap)
					tie_ptn = 15
					if data_tie != -999 :
						tie_ptn = (data_tie - self.minRange) * self.coefRange

					dc.DrawLines(((startX - 5, y), (startX + tie_ptn, y))) 

					#radius = self.tieDotSize / 2.0
					#dc.DrawCircle(startX+20,y, radius)

					dc.DrawLines(((startX, y), (startX, y1))) 

					if affine > 0 :
						dc.DrawLines(((startX - 5, y - 5), (startX, y))) 
						dc.DrawLines(((startX, y), (startX + 5, y - 5))) 
						dc.DrawText(str(affine), startX - 40, y1 - 15)
					else :
						dc.DrawLines(((startX - 5, y + 5), (startX, y))) 
						dc.DrawLines(((startX, y), (startX + 5, y + 5))) 
						dc.DrawText(str(affine), startX - 40, y1 + 5)

			dc.SetPen(wx.Pen(self.colorDict['mcd'], 1))
		else :
			dc.SetPen(wx.Pen(self.colorDict['mbsf'], 1))


		for r in range(len(self.AdjustDepthCore)) :
			if self.AdjustDepthCore[r] == index :
				dc.SetPen(wx.Pen(self.colorDict['mcd'], 1))

		log_number = 1;
		logsmoothed = smoothed

		if smoothed == 3 :
			dc.SetPen(wx.Pen(wx.Colour(238, 216, 174), 1))
			smoothed = 1
		elif smoothed == 2 :
			dc.SetPen(wx.Pen(self.colorDict['smooth'], 1))
		elif smoothed == 5 :
			dc.SetPen(wx.Pen(self.colorDict['log'], 1))
			log_number = 2
			smoothed = 2
		elif smoothed == 6  :
			dc.SetPen(wx.Pen(self.colorDict['mudlineAdjust'], 1))
			log_number = 2
			smoothed = 2
		elif smoothed == 7 :
			dc.SetPen(wx.Pen(wx.Colour(238, 216, 174), 1))
			log_number = 2
			smoothed = 2

		if squish != 100 or self.LogTieData != []:
			self.ELDapplied = True
			if smoothed == 0 :
				dc.SetPen(wx.Pen(self.colorDict['eld'], 1))
			# BLOCK
			#else :
			#dc.SetPen(wx.Pen(wx.Colour(238, 216, 174), 1))

		if self.continue_flag == False :
			#dc.SetPen(wx.Pen(wx.Colour(255, 193, 193), 1))
			dc.SetPen(wx.Pen(wx.Colour(105, 105, 105), 1))

		if quality == "1" :
			dc.SetPen(wx.Pen(wx.Colour(105, 105, 105), 1))

		if smoothed == -1 :
			dc.SetPen(wx.Pen(self.overlapcolorList[self.selectedCount], 1))

		lines = []
		splicelines = []

		# draw nodes
		i = 0	
		px = 0
		py = 0

		si = 0	
		sx = 0
		sy = 0
		spx = 0
		spy = 0
		bottom = -1
		log_min = 999.0
		log_max = -999.0
		spliceholewidth = self.splicerX + (self.holeWidth * log_number) + (50 * log_number) + 50
		y = 0
		
		for r in coreData :
			y, x = r
			if spliceflag == 1 :
				if y >= drawing_start and y <= self.SPrulerEndDepth :
					if bottom == -1 or y <= bottom : 
						sy = self.startDepth + (y - self.SPrulerStartDepth) * (self.length / self.gap)
						sx = x - self.minRange
						sx = (sx * self.coefRange) + spliceholewidth 

						if si > 0 : 
							splicelines.append((spx, spy, sx, sy))
						spx = sx
						spy = sy
						si = si + 1
				elif y > self.SPrulerEndDepth:
					break # no need to continue, this core and all below are out of view

			if compositeflag == 1 :
				if smoothed == 2 :
					if y >= drawing_start and y <= self.SPrulerEndDepth :
						y = self.startDepth + (y - self.SPrulerStartDepth) * (self.length / self.gap)
						x = x - self.minRange
						x = (x * self.coefRange) + spliceholewidth

						if i > 0 : 
							lines.append((px, py, x, y))
						if log_min > x :
							log_min = x
						if log_max < x :
							log_max = x
						px = x
						py = y
						i = i + 1
					elif y > self.SPrulerEndDepth:
						break
				else :
					if y >= drawing_start and y <= self.rulerEndDepth :
						y = self.startDepth + (y - self.rulerStartDepth) * (self.length / self.gap)
						x = x - self.minRange
						x = (x * self.coefRange) + startX 

						if i > 0 : 
							lines.append((px, py, x, y))
						px = x
						py = y
						i = i + 1
						#print "x = " + str(x) + " y = " + str(y) 
					elif y > self.rulerEndDepth:
						break

		min_splice = min - self.minRangeSplice

		if smoothed == 2 :
			min = min - self.minRangeSplice
			min = (min * self.coefRangeSplice) + startX 
			max = max - self.minRangeSplice
			max = (max * self.coefRangeSplice) + startX 
		else :
			min = min - self.minRange
			min = (min * self.coefRange) + startX 
			max = max - self.minRange
			max = (max * self.coefRange) + startX 

		# draw lines 
		y = 0
		if self.DiscretePlotMode == 0 :
			for r in lines :
				px, py, x, y = r
				dc.DrawLines(((px, py), (x, y))) 
		else :
			for r in lines :
				px, py, x, y = r
				dc.DrawCircle(px, py, self.DiscretetSize)

		if smoothed == -1 :
			return

		if y > 0 and quality == "1" :
			dc.DrawText("BAD CORE", startX - 50, y - 20)
		#elif y > 0 and self.continue_flag == False :
		#	dc.DrawText( "DISCRETE CORE", min, y-20)

		if y > 0 and smoothed != 2 :
			dc.DrawText(str(coreno), startX - 20, y - 20)
			dc.SetPen(wx.Pen(self.colorDict['foreground'], 1))
			dc.DrawLines(((startX - 20, y), (startX, y))) 
			if len(annotation) > 0 :
				dc.DrawText(annotation, startX - 35, y - 20)

		if smoothed == 1 :
			for r in splicelines :
				px, py, x, y = r
				dc.DrawLines(((px, py), (x, y))) 
			return


		#min = min - startX
		#max = max - startX

		if smoothed == 2 :
			if log_number != 2 :
				for r in lines :
					l = []
					#l.append( (index, spliceholewidth, r[1], self.holeWidth+40, y-r[1]) )
					l.append((index, min, r[1], max - min, y - r[1], startX, self.holeWidth + 40))
					self.DrawData["SpliceArea"].append(l)
					return
			else :
				for r in lines :
					l = []
					l.append((index, min, r[1], max - min, y - r[1], spliceholewidth, self.holeWidth + 40))
					self.DrawData["LogArea"].append(l)
					return
	
		else : 
			for r in lines :
				l = []
				l.append((index, min, r[1], max - min, y - r[1], startX, self.holeWidth + 40, self.HoleCount))
				#l.append( (index, startX, r[1], self.holeWidth+40, y-r[1]) )
				self.DrawData["CoreArea"].append(l)
				break

		lines = []

		dc.SetPen(wx.Pen(wx.Colour(255, 130, 71), 1))
		y = 0
		for r in splicelines :
			px, py, x, y = r
			dc.DrawLines(((px, py), (x, y))) 

		min = min + spliceholewidth - startX
		max = max + spliceholewidth - startX 

		if y > 0 :
			#min_splice = (min_splice * self.coefRangeSplice) + startX 
			#min_splice = min_splice + self.splicerX + self.spliceHoleWidth - startX
			dc.DrawText(str(hole) + str(coreno), spliceholewidth - 20, y - 20)

		for r in splicelines :
			l = []
			#l.append( (index, spliceholewidth, r[1], self.holeWidth+40, y-r[1]) )
			l.append((index, min, r[1], max - min, y - r[1], spliceholewidth, self.holeWidth + 40))
			self.DrawData["SpliceArea"].append(l)
			break
		splicelines = [] 

		if self.hideTie == 1 :
			return

		if self.guideCore == index : 
			i = 0	
			px = 0
			py = 0
			max = -999
			lead = self.compositeDepth - self.parent.winLength
			lag = self.compositeDepth + self.parent.winLength

			drawing_start = self.rulerStartDepth - 5.0

			for data in self.GuideCore :
				for r in data :
					y, x = r
					if y >= drawing_start and y <= self.rulerEndDepth :
						f = 0
						if y >= lead and y <= lag : 
							f = 1
						y = self.startDepth + (y - self.rulerStartDepth) * (self.length / self.gap)
						x = x - self.minRange
						x = (x * self.coefRange) + startX 
						#if max < x :
						#	max = x
						if i > 0 :	 
							lines.append((px, py, x, y, f))
						px = x
						py = y
						i = i + 1 

			#max = startX + self.holeWidth + 50 
			max = startX + self.holeWidth / 2.0  
			# draw lines 
			if max < self.splicerX :
				for r in lines :
					px, py, x, y, f = r
					if f == 1 : 
						dc.SetPen(wx.Pen(self.colorDict['corrWindow'], 1))
					else : 
						#dc.SetPen(wx.Pen(wx.Colour(0, 139, 0), 1))
						dc.SetPen(wx.Pen(self.colorDict['guide'], 1))
					dc.DrawLines(((px, py), (x, y))) 

		lines = []

		if self.guideSPCore == index : 
			dc.SetBrush(wx.TRANSPARENT_BRUSH)
			dc.SetPen(wx.Pen(wx.Colour(224, 255, 255), 1))
			i = 0	
			px = 0
			py = 0
			lead = self.spliceDepth - self.parent.winLength
			lag = self.spliceDepth + self.parent.winLength

			coefRangeGuide = self.coefRange 
			modifiedType = "splice"
			minRangeGuide = 0.0
			for r in self.range :
				if r[0] == modifiedType :
					minRangeGuide = r[1]
					if r[3] != 0.0 :
						coefRangeGuide = self.holeWidth / r[3]
					else :
						coefRangeGuide = 0 
					break

			for data in self.SPGuideCore :
				for r in data :
					y, x = r
					f = 0
					if y >= lead and y <= lag : 
						f = 1
					y = self.startDepth + (y - self.SPrulerStartDepth) * (self.length / self.gap)
					#x = x - self.minRange
					x = x - minRangeGuide
					x = (x * coefRangeGuide) + self.splicerX + 50
					if i > 0 : 
						lines.append((px, py, x, y, f))
					px = x
					py = y
				i = i + 1 

			# draw lines 
			for r in lines :
				px, py, x, y, f = r
				if f == 1 : 
					#dc.SetPen(wx.Pen(wx.Colour(0, 191, 255), 1))
					dc.SetPen(wx.Pen(self.colorDict['corrWindow'], 1))
				else : 
					#dc.SetPen(wx.Pen(wx.Colour(224, 255, 255), 1))
					dc.SetPen(wx.Pen(self.colorDict['guide'], 1))
				dc.DrawLines(((px, py), (x, y))) 

		lines = [] 

		i = 0
		if spliceflag == 2 and self.LogTieData == []  :
			spliceholewidth = self.splicerX + (self.holeWidth * 2) + 150
			drawing_start = self.rulerStartDepth - 5.0
			for r in coreData :
				y, x = r
				if y >= drawing_start and y <= self.rulerEndDepth :
					y = self.startDepth + (y - self.SPrulerStartDepth) * (self.length / self.gap)
					x = x - self.minRange
					x = (x * self.coefRange) + spliceholewidth
					if i > 0 : 
						lines.append((px, py, x, y))
					px = x
					py = y
					i = i + 1 
			for r in lines :
				px, py, x, y = r
				dc.DrawLines(((px, py), (x, y))) 

		return affine


	def DrawGraphInfo(self, dc, curCoreData, flag):
		dc.SetBrush(wx.TRANSPARENT_BRUSH)
		dc.SetPen(wx.Pen(self.colorDict['foreground'], 1))
		dc.SetTextBackground(self.colorDict['background'])
		dc.SetTextForeground(self.colorDict['foreground'])
		dc.SetFont(self.font2)
		dc.SetPen(wx.Pen(wx.Colour(0, 255, 0), 1))

		x = self.splicerX - 270
		if flag == 2 :
			x = self.Width - 220

		self.minData = -1
		n, leg, site, hole, core, min, max, dmin, dmax, squish, type, quality, holeth = curCoreData
		self.statusStr = self.statusStr + "Hole: " + hole + " Core: " + core
		dc.DrawText("Hole: " + hole + " Core: " + core, x, self.startDepth)
		dc.DrawText("Min: " + str(min) + " Max: " + str(max), x, self.startDepth + 20)
		dc.DrawText("Stretched Ratio: " + str(squish) + "%", x, self.startDepth + 40)

		qualityStr = "Quality: "
		qualityStr += "Good" if quality == '0' else "Bad"
		dc.DrawText(qualityStr, x, self.startDepth + 60) 

		self.minData = min 
		return (type, holeth)


	def DrawMouseInfo(self, dc, curCoreData, x, y, startx, flag, type):
		dc.SetBrush(wx.TRANSPARENT_BRUSH)
		dc.SetPen(wx.Pen(self.colorDict['foreground'], 1))
		dc.SetTextBackground(self.colorDict['background'])
		dc.SetTextForeground(self.colorDict['foreground'])
		dc.SetFont(self.font2)

		ycoord = y
		ycoord = (ycoord - self.startDepth) / (self.length / self.gap) + self.rulerStartDepth
		unroundedYcoord = ycoord
		ycoord = round(ycoord, 3)
		#if flag == 1 :
		#	dc.DrawText(str(ycoord), self.compositeX + 3, y - 5)
		#else :
		#	dc.DrawText(str(ycoord), self.splicerX + 3, y - 5)

		tempx = 0.0
		if type == "Natural Gamma" :
			type = "NaturalGamma"
		for r in self.range :
			if r[0] == type : 
				if r[3] != 0.0 :
					self.coefRange = self.holeWidth / r[3]
				else :
					self.coefRange = 0
				tempx = (x - startx) / self.coefRange + self.minData
				tempx = round(tempx, 3)
				dc.DrawText(str(tempx), x, self.startDepth - 15)
				break

		section = self.parent.GetSectionAtDepth(curCoreData[3], int(curCoreData[4]), type, ycoord)
		self.statusStr += " Section: " + str(section)

		# display depth in ruler units
		yUnitAdjusted = round(unroundedYcoord * self.GetRulerUnitsFactor(), 3)
		self.statusStr += " Depth: " + str(yUnitAdjusted) + " Data: " + str(tempx)

	def DrawAnnotation(self, dc, info, line):
		dc.SetBrush(wx.TRANSPARENT_BRUSH)
		dc.SetPen(wx.Pen(self.colorDict['foreground'], 1))
		dc.SetTextBackground(self.colorDict['background'])
		dc.SetTextForeground(self.colorDict['foreground'])
		dc.SetFont(self.font2)
		dc.SetPen(wx.Pen(wx.Colour(0, 255, 0), 1))
		y = 0
		if line == 1 :
			y = self.Height - 90
		elif line == 2 :
			y = self.Height - 70
		elif line == 3 :
			y = self.Height - 50
		dc.DrawText(info, self.splicerX - 250, y)

	def Draw(self, dc):
		dc.BeginDrawing()
		dc.SetBackground(wx.Brush(self.colorDict['background']))
		dc.Clear() # make sure you clear the bitmap!

		if self.WindowUpdate == 1 : 
			self.Width, self.Height = self.parent.GetClientSizeTuple()
			self.SetSize((self.Width, self.Height))
				
			self.parent.UpdateSize(self.Width, self.Height)

			if self.CLOSEFLAG == 1 :
				self.Width = self.Width - 45 
				self.sidePanel.SetPosition((self.Width, 0))
				self.sidePanel.SetSize((45, self.Height))
				self.sideNote.SetSize((45, self.Height))
			else :
				self.Width = self.Width - self.sideTabSize
				self.sidePanel.SetPosition((self.Width, 0))
				self.sidePanel.SetSize((self.sideTabSize, self.Height))
				self.sideNote.SetSize((self.sideTabSize, self.Height))

			#self.eldPanel.SetPosition((self.Width, 50))
			self.subSideNote.SetSize((self.sideTabSize - 20, self.Height))

			#self.logPanel.SetSize((self.sideTabSize-40,self.Height-50))
			#self.helpPanel.SetSize((self.sideTabSize-40,self.Height-50))
			#self.helpText.SetSize((300,self.Height-50))
			#self.reportText.SetSize((300,self.Height-50))

			if self.spliceWindowOn == 1 :
				if self.splicerX <= self.compositeX :
					self.splicerX = self.Width * 8 / 10 + self.compositeX
				if self.splicerX > (self.Width - 100) :
					self.splicerX = self.Width - 100
			else :
				self.splicerX = self.Width + 45
			self.WindowUpdate = 0


		if self.MainViewMode == True :
			self.DrawMainView(dc)
		else :
			self.DrawAgeDepthView(dc)

		# horizontal scroll bar
		dc.SetBrush(wx.Brush(wx.Colour(205, 201, 201)))
		dc.SetPen(wx.Pen(wx.Colour(205, 201, 201), 1))

		if self.spliceWindowOn == 1 :
			dc.DrawRectangle(self.compositeX, self.Height - self.ScrollSize, self.splicerX - 60 - self.compositeX, self.ScrollSize)
			dc.DrawRectangle(self.Width - self.ScrollSize - 1, 0, self.ScrollSize, self.Height)
			dc.DrawRectangle(self.splicerX, self.Height - self.ScrollSize, self.Width - self.splicerX, self.ScrollSize)
			dc.DrawRectangle(self.splicerX - self.ScrollSize - 45, 0, self.ScrollSize, self.Height)
		else :
			dc.DrawRectangle(self.compositeX, self.Height - self.ScrollSize, self.Width - 10 - self.compositeX, self.ScrollSize)
			dc.DrawRectangle(self.Width - self.ScrollSize - 1, 0, self.ScrollSize, self.Height)

		dc.SetTextForeground(wx.BLACK)
		if self.MainViewMode == True :
			dc.SetPen(wx.Pen(self.colorDict['mbsf'], 1))
			dc.SetBrush(wx.Brush(self.colorDict['mbsf']))
			paintgap = 50 
			start = self.Width - 210
			if self.spliceWindowOn == 1 :
				start = self.splicerX - 210
			else :
				start = start + 45

			y = self.Height - self.ScrollSize
			dc.DrawRectangle(start, y, paintgap, self.ScrollSize)
			dc.DrawText("mbsf", start, y)
			start = start + paintgap
			dc.SetPen(wx.Pen(self.colorDict['mcd'], 1))
			dc.SetBrush(wx.Brush(self.colorDict['mcd']))
			dc.DrawRectangle(start, y, paintgap, self.ScrollSize)
			dc.DrawText("mcd", start, y)
			start = start + paintgap
			dc.SetPen(wx.Pen(self.colorDict['eld'], 1))
			dc.SetBrush(wx.Brush(self.colorDict['eld']))
			dc.DrawRectangle(start, y, paintgap, self.ScrollSize)
			dc.DrawText("eld", start, y)

			if self.spliceWindowOn == 1 :
				dc.SetPen(wx.Pen(self.colorDict['splice'], 1))
				dc.SetBrush(wx.Brush(self.colorDict['splice']))
				paintgap = (self.Width - self.splicerX) / 5.0
				if paintgap > 50 :
					paintgap = 50 
				start = self.splicerX
				y = self.Height - self.ScrollSize
				dc.DrawRectangle(start, y, paintgap, self.ScrollSize)
				dc.DrawText("splice", start, y)
				start = start + paintgap
				dc.SetPen(wx.Pen(self.colorDict['log'], 1))
				dc.SetBrush(wx.Brush(self.colorDict['log']))
				paintgap = paintgap + paintgap / 2
				dc.DrawRectangle(start, y, paintgap, self.ScrollSize)
				dc.DrawText("eld + log", start, y)
				start = start + paintgap
				paintgap = paintgap * 2 
				dc.SetPen(wx.Pen(self.colorDict['mudlineAdjust'], 1))
				dc.SetBrush(wx.Brush(self.colorDict['mudlineAdjust']))
				dc.DrawRectangle(start, y, paintgap, self.ScrollSize)
				dc.DrawText("mudline adjusted log", start, y)
		else :
			dc.SetPen(wx.Pen(self.colorDict['paleomag'], 1))
			dc.SetBrush(wx.Brush(self.colorDict['paleomag']))
			paintgap = 80 
			start = self.splicerX - 460
			y = self.Height - self.ScrollSize
			dc.DrawRectangle(start, y, paintgap, self.ScrollSize)
			dc.DrawText("paleomag", start, y)
			start = start + paintgap
			dc.SetPen(wx.Pen(self.colorDict['diatom'], 1))
			dc.SetBrush(wx.Brush(self.colorDict['diatom']))
			dc.DrawRectangle(start, y, paintgap, self.ScrollSize)
			dc.DrawText("diatoms", start, y)
			start = start + paintgap
			dc.SetPen(wx.Pen(self.colorDict['rad'], 1))
			dc.SetBrush(wx.Brush(self.colorDict['rad']))
			dc.DrawRectangle(start, y, paintgap, self.ScrollSize)
			dc.DrawText("radioloria", start, y)
			start = start + paintgap
			dc.SetPen(wx.Pen(self.colorDict['foram'], 1))
			dc.SetBrush(wx.Brush(self.colorDict['foram']))
			dc.DrawRectangle(start, y, paintgap, self.ScrollSize)
			dc.DrawText("foraminifera", start, y)
			start = start + paintgap
			dc.SetPen(wx.Pen(self.colorDict['nano'], 1))
			dc.SetBrush(wx.Brush(self.colorDict['nano']))
			dc.DrawRectangle(start, y, paintgap, self.ScrollSize)
			dc.DrawText("nannofossils", start, y)
			if self.spliceWindowOn == 1 :
				dc.SetPen(wx.Pen(self.colorDict['splice'], 1))
				dc.SetBrush(wx.Brush(self.colorDict['splice']))
				paintgap = (self.Width - self.splicerX) / 3.0
				if paintgap > 50 :
					paintgap = 50 
				start = self.splicerX
				y = self.Height - self.ScrollSize
				dc.DrawRectangle(start, y, paintgap, self.ScrollSize)
				dc.DrawText("splice", start, y)
				start = start + paintgap
				paintgap = paintgap * 2.5 
				dc.SetPen(wx.Pen(wx.Colour(0, 139, 0), 1))
				dc.SetBrush(wx.Brush(wx.Colour(0, 139, 0)))
				dc.DrawRectangle(start, y, paintgap, self.ScrollSize)
				dc.DrawText("sedimentation rate", start, y)

		# Here's the actual drawing code.
		for key, data in self.DrawData.items():
			if key == "Skin":
				bmp, x, y = data
				dc.DrawBitmap(bmp, self.Width + x - 1, y, 1)
			elif key == "HScroll":
				bmp, x, y = data
				dc.DrawBitmap(bmp, x, self.Height + y, 1)

		# Here's the actual drawing code.
		if self.spliceWindowOn == 1 and "MovableSkin" in self.DrawData:
			bmp, x, y = self.DrawData["MovableSkin"]
			x = x + self.splicerX - 40
			dc.DrawBitmap(bmp, x, y, 1)

		if self.mode == 1 : 
			self.statusStr = "Composite mode	 "
		elif self.mode == 2 : 
			self.statusStr = "Splice mode		 "
		elif self.mode == 3 : 
			self.statusStr = "Core-log matching mode		 "
		elif self.mode == 4 : 
			self.statusStr = "Age depth mode		 "

		holeth = -1
		type = ""
		for key, data in self.DrawData.items():
			if key == "MouseInfo":
				for r in data:
					coreIndex, x, y, startx, flag = r
					coreFound = False
					curCoreData = []
					for dataList in self.DrawData["CoreInfo"]:
						for coreData in dataList:
								if coreData[0] == coreIndex:
									curCoreData = coreData
									coreFound = True
									break
						if coreFound == True:
							break

					if coreFound == True:
						type, holeth = self.DrawGraphInfo(dc, curCoreData, flag)
						self.selectedHoleType = type
						self.DrawMouseInfo(dc, curCoreData, x, y, startx, flag, type)
			if type != "" :
				break
		self.parent.statusBar.SetStatusText(self.statusStr)

		self.selectedHoleType = type

		if self.MousePos != None :
			dc.SetBrush(wx.TRANSPARENT_BRUSH)
			dc.SetPen(wx.Pen(self.colorDict['foreground'], 1))
			dc.SetTextBackground(self.colorDict['background'])
			dc.SetTextForeground(self.colorDict['foreground'])
			#dc.SetFont( self.font2 )
			ycoord = self.MousePos[1] 
			ycoord = (ycoord - self.startDepth) / (self.length / self.gap) + self.rulerStartDepth
			ycoord = ycoord * self.GetRulerUnitsFactor()
			ycoord = round(ycoord, 3)
			if self.MousePos[0] < self.splicerX :
				if holeth != -1 :
					dc.DrawText(str(ycoord), self.WidthsControl[holeth], self.MousePos[1] - 5)
				else :
					dc.DrawText(str(ycoord), self.compositeX + 3, self.MousePos[1] - 5)
				if self.showGrid == True :
					dc.SetPen(wx.Pen(self.colorDict['foreground'], 1, style=wx.DOT))
					dc.DrawLines(((self.compositeX, self.MousePos[1] - 5), (self.splicerX - 50, self.MousePos[1] - 5)))
			elif self.MousePos[0] <= self.Width: # 1/29/2014 brg: Don't draw depth info if we're over options tab
				dc.DrawText(str(ycoord), self.splicerX + 3, self.MousePos[1] - 5)
				if self.showGrid == True :
					dc.SetPen(wx.Pen(self.colorDict['foreground'], 1, style=wx.DOT))
					dc.DrawLines(((self.splicerX, self.MousePos[1] - 5), (self.Width, self.MousePos[1] - 5)))

			#self.MousePos = None

		dc.EndDrawing()
			
		
	def DrawAgeDepthView(self, dc):
		# Draw LINE
		#for data in self.AgeDataList :
		#	idx, start, rawstart, age, name, type, sedrate = data
		#	self.AgeSpliceGap = start * self.AgeUnit / age
		#	break

		dc.SetPen(wx.Pen(wx.RED, 1))
		preX = self.compositeX + ((self.firstPntAge - self.minAgeRange) * self.ageLength) + self.AgeShiftX
		preY = self.startAgeDepth + (self.firstPntDepth - self.rulerStartAgeDepth) * (self.ageYLength / self.ageGap) + self.AgeShiftY
		for data in self.AgeDataList :
			idx, start, rawstart, age, name, label, type, sed = data 
			if self.mbsfDepthPlot == 1 : # if mbsf
				start = rawstart
			x = self.compositeX + ((age - self.minAgeRange) * self.ageLength) + self.AgeShiftX
			y = self.startAgeDepth + (start - self.rulerStartAgeDepth) * (self.ageYLength / self.ageGap) + self.AgeShiftY
			dc.DrawLines(((preX, preY), (x, y)))
			preX = x
			preY = y 

		# Draw Age DOTs
		dc.SetFont(self.font3)
		self.DrawData["CoreArea"] = []
		index = 0
		for data in self.StratData :
			for r in data:
				order, hole, name, label, start, stop, rawstart, rawstop, age, type = r
				mcdstart = start
				if self.mbsfDepthPlot == 1 : # if mbsf 
					start = rawstart
					stop = rawstop
				if type == 0 :  #DIATOMS 
					dc.SetPen(wx.Pen(self.colorDict['diatom'], 1))
					dc.SetBrush(wx.Brush(self.colorDict['diatom']))
				elif type == 1 : #RADIOLARIA
					dc.SetPen(wx.Pen(self.colorDict['rad'], 1))
					dc.SetBrush(wx.Brush(self.colorDict['rad']))
					#dc.SetTextForeground(self.colorDict['rad'])
				elif type == 2 : #FORAMINIFERA
					dc.SetPen(wx.Pen(self.colorDict['foram'], 1))
					dc.SetBrush(wx.Brush(self.colorDict['foram']))
					#dc.SetTextForeground(self.colorDict['foram'])
				elif type == 3 : #NANNOFOSSILS
					dc.SetPen(wx.Pen(self.colorDict['nano'], 1))
					dc.SetBrush(wx.Brush(self.colorDict['nano']))
					#dc.SetTextForeground(self.colorDict['nano'])
				elif type == 4 : #PALEOMAG
					dc.SetPen(wx.Pen(self.colorDict['paleomag'], 1))
					dc.SetBrush(wx.Brush(self.colorDict['paleomag']))
					#dc.SetTextForeground(self.colorDict['paleomag'])

				x = self.compositeX + ((age - self.minAgeRange) * self.ageLength) + self.AgeShiftX
				y = self.startAgeDepth + (start - self.rulerStartAgeDepth) * (self.ageYLength / self.ageGap) + self.AgeShiftY
				#y2 = self.startAgeDepth + (stop- self.rulerStartAgeDepth) * ( self.ageYLength / self.ageGap )

				if self.SelectedAge == index : 
					dc.SetPen(wx.Pen(wx.WHITE, 1))
					dc.SetBrush(wx.Brush(wx.WHITE))
					if self.AgeEnableDrag == 0 :
						dc.DrawLines(((x, self.startAgeDepth), (x, y)))
						dc.DrawLines(((self.compositeX, y), (x, y)))
						dc.SetTextForeground(self.colorDict['foreground'])
						dc.DrawText(str(age), x - 25, self.startAgeDepth)
						dc.DrawText(str(start), self.compositeX + 3, y - 15)
						dc.DrawText(str(age), x + 15, y - 15)
						dc.SetTextForeground(wx.BLACK)

				if x >= self.compositeX and x <= self.splicerX :
					dc.DrawCircle(x, y, 12)
					dc.DrawText(label, x - 5, y - 5)
				l = []
				l.append((index, x - 7, y - 7, 12, 12, -1, -1, -1))
				self.DrawData["CoreArea"].append(l)
				#dc.DrawLines(((x, y),(x, y2)))
				index = index + 1

		dc.SetBrush(wx.Brush(wx.Colour(255, 215, 0)))
		dc.SetPen(wx.Pen(wx.Colour(255, 215, 0), 1))
		for data in self.UserdefStratData :
			for r in data:
				name, start, rawstart, age, comment = r
				if self.mbsfDepthPlot == 1 : # if mbsf 
					start = rawstart
				x = self.compositeX + ((age - self.minAgeRange) * self.ageLength) + self.AgeShiftX
				y = self.startAgeDepth + (start - self.rulerStartAgeDepth) * (self.ageYLength / self.ageGap) + self.AgeShiftY

				if self.SelectedAge == index : 
					dc.SetPen(wx.Pen(wx.WHITE, 1))
					dc.SetBrush(wx.Brush(wx.WHITE))
					if self.AgeEnableDrag == 0 :
						dc.DrawLines(((x, self.startAgeDepth), (x, y)))
						dc.DrawLines(((self.compositeX, y), (x, y)))
						dc.SetTextForeground(self.colorDict['foreground'])
						dc.DrawText(str(age), x - 25, self.startAgeDepth)
						dc.DrawText(str(start), self.compositeX + 3, y - 15)
						dc.DrawText(str(age), x + 15, y - 15)
						dc.SetTextForeground(wx.BLACK)
				else :
					dc.SetBrush(wx.Brush(wx.Colour(255, 215, 0)))
					dc.SetPen(wx.Pen(wx.Colour(255, 215, 0), 1))

				if x >= self.compositeX and x <= self.splicerX :
					dc.DrawCircle(x, y, 12)
					if len(name) > 2 :
						name = name[0] + name[1]
					dc.DrawText(name, x - 5, y - 5)

				l = []
				l.append((index, x - 7, y - 7, 12, 12, -1, -1, -1))
				self.DrawData["CoreArea"].append(l)
				index = index + 1


		dc.SetBrush(wx.Brush(self.colorDict['background']))
		dc.SetPen(wx.Pen(self.colorDict['background'], 1))
		dc.DrawRectangle(0, 0, self.compositeX, self.Height)
		dc.DrawRectangle(0, 0, self.Width, self.startAgeDepth)
		dc.DrawRectangle(self.splicerX - 45, 0, self.Width - self.splicerX, self.Height)
		dc.DrawRectangle(self.splicerX - 45, 0, self.Width, self.startAgeDepth)
		self.DrawAgeModelRuler(dc)

		# Draw ORIGIN
		dc.SetBrush(wx.Brush(wx.Colour(255, 215, 0)))
		dc.SetPen(wx.Pen(wx.Colour(255, 215, 0), 1))
		x = self.compositeX + ((self.firstPntAge - self.minAgeRange) * self.ageLength) + self.AgeShiftX
		y = self.startAgeDepth + (self.firstPntDepth - self.rulerStartAgeDepth) * (self.ageYLength / self.ageGap) + self.AgeShiftY
		if x >= self.compositeX and x <= self.splicerX :
			if y > (self.startAgeDepth - 10) :
				dc.DrawCircle(x, y, 5)

		dc.SetTextForeground(self.colorDict['foreground'])
		if self.spliceWindowOn == 1 :
			self.DrawAgeYRate(dc)
			smooth_flag = 0 

			splice_smooth = -1
			for r in self.range :
				if r[0] == 'splice':
					splice_smooth = r[4]
					break

			#self.AgeSpliceHole = False
			if self.AgeSpliceHole == True :
				if splice_smooth != 1 :
					for data in self.SpliceData:
						for r in data:
							hole = r 
							self.DrawSplice(dc, hole, smooth_flag)
				if splice_smooth != 0 :
					smooth_flag = 1 
					if len(self.SpliceData) > 0 : 
						smooth_flag = 2 
					for data in self.SpliceSmoothData:
						for r in data:
							hole = r 
							self.DrawSplice(dc, hole, smooth_flag)
			else :
				if len(self.LogSpliceData) == 0 :
					if splice_smooth != 1 :
						for data in self.SpliceData:
							for r in data:
								hole = r 
								self.DrawSplice(dc, hole, smooth_flag)

					if splice_smooth != 0 :
						smooth_flag = 1 
						if len(self.SpliceData) > 0 : 
							smooth_flag = 2 
						for data in self.SpliceSmoothData:
							for r in data:
								hole = r 
								self.DrawSplice(dc, hole, smooth_flag)
				else :
					if splice_smooth != 1 :
						for data in self.LogSpliceData :
							for r in data:
								hole = r 
								self.DrawSplice(dc, hole, smooth_flag)
					if splice_smooth != 0 :
						smooth_flag = 1 
						if len(self.SpliceData) > 0 : 
							smooth_flag = 2 
						for data in self.LogSpliceSmoothData :
							for r in data:
								hole = r 
								self.DrawSplice(dc, hole, smooth_flag)

		dc.SetBrush(wx.Brush(self.colorDict['background']))
		dc.SetPen(wx.Pen(self.colorDict['background'], 1))
		dc.DrawRectangle(self.splicerX - 45, 0, self.Width, self.startAgeDepth - 20)
		dc.DrawText("Age", self.splicerX - 35, 20)
		dc.DrawText("(Ma)", self.splicerX - 35, 30)
		dc.SetPen(wx.Pen(self.colorDict['foreground'], 1))
		dc.DrawLines(((self.splicerX, 0), (self.splicerX, self.startAgeDepth)))
		dc.DrawText("Splice ", self.splicerX + 50, 25)
		dc.DrawText("Sedimentation Rate", self.splicerX + self.holeWidth + 150, 5)
		dc.DrawText("(m/Ma)", self.splicerX + self.holeWidth + 150, 25)


	def BUILD_AGEMODEL(self, order, age_name, age_depth, age_age):
		idx = 0
		for data in self.StratData :
			for r in data:
				#order, hole, name, label, start, stop, rawstart, rawstop, age, type = r
				if r[3] == age_name and r[6] == age_depth and r[8] == age_age :
					self.AgeDataList.insert(order, (idx, r[4], r[6], r[8], r[2], r[3], r[9], 0.0)) 
					return True 
			idx = idx + 1

		return False 

	def CHECK_AGE(self, age_name, age_depth, age_age):
		for data in self.StratData :
			for r in data:
				#order, hole, name, label, start, stop, rawstart, rawstop, age, type = r
				if r[3] == age_name and r[6] == age_depth and r[8] == age_age :
					return True 
		return False 


	def GetAGENAME(self, age_depth, age_age):
		for data in self.StratData :
			for r in data:
				#order, hole, name, label, start, stop, rawstart, rawstop, age, type = r
				if r[6] == age_depth and r[8] == age_age :
					return r[3], r[9] 
		for data in self.UserdefStratData :
			for r in data:
				#name, mcd, depth, age, comment = r
				if r[2] == age_depth and r[3] == age_age :
					return r[0], "handpick" 
		return None 


	def AddUserdefAge(self, name, depth, mcd, age, comment):
		l = []
		l.append((name, mcd, depth, age, comment))
		self.UserdefStratData.append(l)


	def AddToAgeList(self, name, depth, mcd, age, order, type):
		self.AgeDataList.insert(order, (-1, mcd, depth, age, type, name, -1, 0.0))


	def DrawAgeYRate(self, dc):
		dc.SetPen(wx.Pen(wx.Colour(255, 215, 0), 1, style=wx.DOT))
		width = self.holeWidth 
		sx = self.splicerX + 50 
		y = (self.firstPntAge / self.AgeUnit) * self.AgeSpliceGap 
		sy = self.startAgeDepth + (y - self.SPrulerStartAgeDepth) * (self.spliceYLength / self.gap) + self.AgeShiftY
		dc.DrawLines(((sx, sy), (sx + width, sy)))
		dc.DrawText("X", sx + width + 10, sy - 5)
		prevy = sy
		prevdepth = y
		prevage = 0.0
		
		self.AgeYRates = []
		offset = 0.0
		prevRate = 1.0
		count = 0
		prevsedrate = 0.0
		prevagey = (prevage / self.AgeUnit) * self.AgeSpliceGap 
		sedrate_size = 2
		sedrate_width = 220
		sedrate100 = 0.0

		prevdepth = (self.firstPntAge / self.AgeUnit) * self.AgeSpliceGap 
		self.AdjustAgeDepth = prevdepth - self.firstPntDepth 
		prevdepth = self.firstPntDepth
		prevage = self.firstPntAge

		for agedata in self.AgeDataList :
			n, mcd, mbsf, age, name, label, type, sed = agedata
			depth = mcd

			agey = (age / self.AgeUnit) * self.AgeSpliceGap 
			sy = self.startAgeDepth + (agey - self.SPrulerStartAgeDepth) * (self.spliceYLength / self.gap)
			dc.SetPen(wx.Pen(wx.Colour(255, 215, 0), 1, style=wx.DOT))
			dc.DrawLines(((sx, sy), (sx + width, sy)))

			# at age ruler, point the position
			dc.SetPen(wx.Pen(wx.Colour(255, 255, 255), 1))
			dc.DrawLines(((self.splicerX - 5, sy), (self.splicerX, sy)))
			dc.DrawText(label + "(" + str(age) + ")", sx + width + 10, sy - 5)

			# draw sedrate
			if (prevage - age) != 0 :
				sedrate = (prevdepth - depth) / (prevage - age)
			else : 
				# ??? not sure
				sedrate = (prevdepth - depth) 

			sedrate100 = int(100.0 * float(sedrate)) / 100.0
			self.AgeDataList.pop(count)
			self.AgeDataList.insert(count, ((n, mcd, mbsf, age, name, label, type, sedrate100)))
			
			dc.SetPen(wx.Pen(wx.Colour(0, 139, 0), 1))
			sedx = sx + width + sedrate_width + sedrate * sedrate_size

			tempsedx = int(100.0 * float(sedrate)) / 100.0;
			dc.DrawText(str(tempsedx), sedx + 5, prevy + 5)

			dc.DrawLines(((sedx, prevy), (sedx, sy)))
			if count > 0 :
				sedxx = sx + width + sedrate_width + prevsedrate * sedrate_size
				dc.DrawLines(((sedxx, prevy), (sedx, prevy)))

			self.AgeYRates.append((depth, age, label))

			count = count + 1
			prevy = sy
			prevdepth = depth 
			prevage = age
			prevsedrate = sedrate
			prevagey = agey


	def DrawMainView(self, dc):
		self.DrawData["CoreArea"] = [] 
		self.DrawData["SpliceArea"] = [] 
		self.DrawData["LogArea"] = [] 
		self.DrawData["CoreInfo"] = [] 

		if self.ScrollUpdate == 1 : 
			self.UpdateScroll(1)
			self.ScrollUpdate = 0 

		self.smooth_id = -1
		self.ELDapplied = False 
		self.WidthsControl = [] 
		self.HoleCount = 0
		self.coreCount = 0 
		self.newHoleX = 30.0
		self.Done = False
		icount = 0
		type = ""

		for data in self.HoleData:
			for r in data:
				hole = r 
				type = self.DrawHoleGraph(dc, hole, 0, type) 
				self.HoleCount = self.HoleCount + 1 
			icount = icount + 1
		self.Done = True

		self.HoleCount = 0
		self.coreCount = 0 
		self.newHoleX = 30.0
		smooth_flag = 3 
		icount = 0
		type = ""
		if len(self.HoleData) == 0 : 
			smooth_flag = 1 
		for data in self.SmoothData:
			for r in data:
				hole = r 
				type = self.DrawHoleGraph(dc, hole, smooth_flag, type) 
				self.HoleCount = self.HoleCount + 1 
			icount = icount + 1

		self.HoleCount = -2 
		# Drawing Black Box for Erasing the Parts
		dc.SetBrush(wx.Brush(self.colorDict['background']))
		dc.SetPen(wx.Pen(self.colorDict['background'], 1))
		dc.DrawRectangle(0, 0, self.compositeX, self.Height)

		if self.spliceWindowOn == 1 :
			dc.DrawRectangle(self.splicerX - 45, 0, 45, self.Height)
			#dc.DrawRectangle(self.splicerX-45, 0, self.Width, self.Height)
			dc.DrawRectangle(self.splicerX - 45, 0, self.Width, self.startDepth)

			for data in self.AltSpliceData:
				for r in data:
					hole = r 
					self.DrawSplice(dc, hole, 7)

			self.splice_smooth_flag = 0 
			splice_data = []
			for r in self.range :
				if r[0] == 'splice':
					self.splice_smooth_flag = r[4] 

			splice_data = []
			if self.splice_smooth_flag == 1 :
				splice_data = self.SpliceSmoothData
			else :
				splice_data = self.SpliceData
			smooth_flag = 0 
			if self.ShowSplice == True :
				for data in splice_data:
					for r in data:
						hole = r 
						self.DrawSplice(dc, hole, smooth_flag)

				if self.ShowLog == True and self.LogData != [] and self.LogSpliceData == [] :
					for data in splice_data:
						for r in data:
							hole = r 
							self.DrawSplice(dc, hole, 3)
							self.DrawSplice(dc, hole, 4)
				elif self.ShowLog == True :
					log_splice_data = []
					if self.splice_smooth_flag == 1 :
						log_splice_data = self.LogSpliceSmoothData
					else :
						log_splice_data = self.LogSpliceData
					#for data in self.LogSpliceData:
					for data in log_splice_data:
						for r in data:
							hole = r 
							self.DrawSplice(dc, hole, 3)
							self.DrawSplice(dc, hole, 4)

				splice_data = []
				if self.splice_smooth_flag == 2 :
					splice_data = self.SpliceSmoothData

				smooth_flag = 1 
				if len(self.SpliceData) > 0 : 
					smooth_flag = 2 
				for data in splice_data:
					for r in data:
						hole = r 
						self.DrawSplice(dc, hole, smooth_flag)

				if self.ShowLog == True and self.LogData != [] :
					log_splice_data = []
					if self.splice_smooth_flag == 2 :
						log_splice_data = self.LogSpliceSmoothData

					if self.LogSpliceSmoothData == [] :
						for data in splice_data:
							for r in data:
								hole = r 
								self.DrawSplice(dc, hole, 5)
								self.DrawSplice(dc, hole, 6)
					else : 
						#for data in self.LogSpliceSmoothData:
						for data in log_splice_data:
							for r in data:
								hole = r 
								self.DrawSplice(dc, hole, 5)
								self.DrawSplice(dc, hole, 6)

			if self.ShowLog == True :
				log_smooth_flag = 0 
				log_data = []
				for r in self.range :
					if r[0] == 'log':
						log_smooth_flag = r[4] 

				log_data = []
				if log_smooth_flag == 1 :
					log_data = self.LogSMData
				else :
					log_data = self.LogData

				if self.isLogShifted == False :
					#for data in self.LogData:
					for data in log_data:
						for r in data:
							hole = r 
							#self.DrawHoleGraph(dc, hole, 5, self.logHoleWidth) 
							self.DrawHoleGraph(dc, hole, 5, None)
					log_data = []
					if log_smooth_flag == 2 :
						log_data = self.LogSMData
					#for data in self.LogSMData:
					for data in log_data:
						for r in data:
							hole = r 
							self.DrawHoleGraph(dc, hole, 7, None)
				else :
					#for data in self.LogData:
					for data in log_data:
						for r in data:
							hole = r 
							#self.DrawHoleGraph(dc, hole, 6, self.logHoleWidth) 
							self.DrawHoleGraph(dc, hole, 6, None)
					log_data = []
					if log_smooth_flag == 2 :
						log_data = self.LogSMData
					#for data in self.LogSMData:
					for data in log_data:
						for r in data:
							hole = r 
							self.DrawHoleGraph(dc, hole, 7, None)

		if self.ShowStrat == True :
			self.DrawStratCore(dc, False)
			if len(self.SpliceData) > 0 :
				self.DrawStratCore(dc, True)

		self.DrawRuler(dc)

		tempx = 0
		if self.hideTie == 0 : 
			x = 0
			x0 = 0
			y = 0
			y0 = 0
			count = 0
			radius = self.tieDotSize / 2

			for data in self.TieData:
				if count == 0 : 
					dc.SetBrush(wx.Brush(self.colorDict['fixedTie']))
					dc.SetPen(wx.Pen(self.colorDict['fixedTie'], 1))
				elif count == 1 : 
					dc.SetBrush(wx.Brush(self.colorDict['shiftTie']))
					dc.SetPen(wx.Pen(self.colorDict['shiftTie'], 1))

				for r in data :
					y = self.startDepth + (r[6] - self.rulerStartDepth) * (self.length / self.gap)
					tempx = r[6] 
					tempx = round(tempx, 3)

					x = (r[0] * self.holeWidth) + (r[0] * 50) + 50 - self.minScrollRange + 40 

					if r[6] >= self.rulerStartDepth and r[6] <= self.rulerEndDepth :
						if x < (self.splicerX - self.holeWidth / 2) :
							dc.DrawCircle(x, y, radius)
							if count == 0 : 
								dc.SetPen(wx.Pen(self.colorDict['fixedTie'], self.tieline_width, style=wx.DOT))
							elif count == 1 : 
								dc.DrawRectangle(x + self.holeWidth - radius, y - radius, self.tieDotSize, self.tieDotSize)
								dc.SetPen(wx.Pen(self.colorDict['shiftTie'], self.tieline_width, style=wx.DOT))

							dc.DrawLine(x, y, x + self.holeWidth, y)
							dc.DrawText(str(tempx), x - 45, y) 
				if count == 1 and r[6] >= self.rulerStartDepth and r[6] <= self.rulerEndDepth :
					count = -1 
				x0 = x
				y0 = y 
				count = count + 1

			if self.spliceWindowOn == 1 :
				count = 0
				diff = 0
				dc.SetTextBackground(self.colorDict['background'])
				dc.SetTextForeground(self.colorDict['foreground'])
				for data in self.SpliceTieData:
					x = self.splicerX + 50 
					if count == 0 : 
						dc.SetBrush(wx.Brush(self.colorDict['fixedTie']))
						dc.SetPen(wx.Pen(self.colorDict['fixedTie'], 1))
					elif count == 1 : 
						dc.SetBrush(wx.Brush(self.colorDict['shiftTie']))
						dc.SetPen(wx.Pen(self.colorDict['shiftTie'], 1))
						x += self.holeWidth + 50
					for r in data :
						y = self.startDepth + (r[6] - self.SPrulerStartDepth) * (self.length / self.gap)
						tempx = r[6]
						tempx = round(tempx, 3)

						if r[6] >= self.SPrulerStartDepth and r[6] <= self.SPrulerEndDepth :
							dc.DrawCircle(x + diff, y, radius)
							if count == 0 : 
								dc.SetPen(wx.Pen(self.colorDict['fixedTie'], self.tieline_width, style=wx.DOT))
								dc.DrawLine(x, y, x + self.holeWidth + 50, y)
							elif count == 1 : 
								dc.DrawRectangle(x + self.holeWidth - radius, y - radius, self.tieDotSize, self.tieDotSize)
								if r[9] == 0 :
									dc.SetPen(wx.Pen(self.colorDict['shiftTie'], self.tieline_width + 1))
									dc.DrawLine(x0 + diff + self.holeWidth + 50, y0, x + diff, y)

								dc.SetPen(wx.Pen(self.colorDict['shiftTie'], self.tieline_width, style=wx.DOT))
								dc.DrawLine(x, y, x + self.holeWidth, y)

							dc.SetPen(wx.Pen(self.colorDict['foreground'], 1))
					if count == 1 and r[6] >= self.SPrulerStartDepth and r[6] <= self.SPrulerEndDepth :
						count = -1 
					x0 = x
					y0 = y 
					count = count + 1
					if count >= 2 :
						count = 0


				if self.SpliceData == [] and self.SpliceSmoothData == [] :
					return

				count = 0
				tie_index = 0
				for data in self.LogTieData:
					dc.SetPen(wx.Pen(self.colorDict['foreground'], 1))
					dc.SetTextBackground(self.colorDict['background'])
					dc.SetTextForeground(self.colorDict['foreground'])
					dc.SetBrush(wx.Brush(self.colorDict['shiftTie']))
					dc.SetPen(wx.Pen(self.colorDict['shiftTie'], 1))
					for r in data :
						y = self.startDepth + (r[6] - self.SPrulerStartDepth) * (self.length / self.gap)
						x = self.splicerX + self.holeWidth + 100 
						if count == 0 : 
							dc.SetBrush(wx.Brush(self.colorDict['fixedTie']))
							dc.SetPen(wx.Pen(self.colorDict['fixedTie'], 1))
						elif count == 1 : 
							x += self.holeWidth + 50
							dc.SetBrush(wx.Brush(self.colorDict['shiftTie']))
							dc.SetPen(wx.Pen(self.colorDict['shiftTie'], 1))
						dc.DrawCircle(x, y, radius)
						if count == 0 : 
							if self.Highlight_Tie == tie_index :
								dc.SetPen(wx.Pen(self.colorDict['fixedTie'], self.tieline_width))
							else :
								dc.SetPen(wx.Pen(self.colorDict['fixedTie'], self.tieline_width, style=wx.DOT))
							dc.DrawLine(x, y, x + self.holeWidth + 50, y)
						elif count == 1 : 
							dc.DrawRectangle(x + self.holeWidth - radius, y - radius, self.tieDotSize, self.tieDotSize)
							if self.Highlight_Tie == tie_index :
								dc.SetPen(wx.Pen(self.colorDict['shiftTie'], self.tieline_width))
							else :
								dc.SetPen(wx.Pen(self.colorDict['shiftTie'], self.tieline_width, style=wx.DOT))
							dc.DrawLine(x, y, x + self.holeWidth, y)

						dc.SetPen(wx.Pen(self.colorDict['foreground'], 1))
						tempx = r[6]
						tempx = round(tempx, 3)

						if count == 1 :
							x0 = r[0] - self.holeWidth
							
						if count == 1 : 
							tie_index += 1 
							count = -1 
						x0 = x
						y0 = y 
						count = count + 1


	def GrabCore(self, coreindex, type, depth_t, depth_b) :
		hole = '-'
		coreid = -1
		ret = 0
		top = -1.0
		bottom = -1.0
		for s in self.DrawData["CoreInfo"]:
			data = s
			for r in data:
				if r[0] == coreindex :
				 hole = r[3]
				 coreid = int(r[4])
				 top = float(r[7])
				 bottom = float(r[8])
				 ret = 1
				 break
			if ret == 1:
				break

		if type == 1 : # ABOVE 
			bottom = depth_b
		elif type == 2 : # BELOW 
			top = depth_t
		elif type == 3 : # BETWEEN
			if depth_b > depth_t :
				bottom = depth_b
				top = depth_t
			else :
				bottom = depth_t
				top = depth_b
		l = []
		l.append((self.SpliceCoreId, hole, coreid, top, bottom)) 
		self.SplicedHole.append(l)


	def SetSaganFromFile(self, tie_list):
		self.LogTieData = []
		for tie_data in tie_list : 
			id, holeB, coreB, holeA, coreA, depth, depthB = tie_data 
			coreid = 0
			count = 0
			for data in self.DrawData["CoreInfo"]:
				for r in data:
					if r[3] == holeA and r[4] == str(coreA):
						coreid = int(r[0])
						count = 1 
						break
				if count == 1:
					break
			# mousex, y, core id, fixed, startX, mindata, depth, splicerX, id, depth
			x = 100 + self.splicerX + self.holeWidth
			y = self.startDepth + (depthB - self.SPrulerStartDepth) * (self.length / self.gap)
			l = []
			l.append((x, y, coreid, 1, -1, -1, depth, self.splicerX, id, depth))
			self.LogTieData.append(l)

			l = []
			x = x + self.holeWidth 
			y = self.startDepth + (depth - self.SPrulerStartDepth) * (self.length / self.gap)
			l.append((x, y, coreid, 0, -1, -1, depth, self.splicerX, id, depth))
			self.LogTieData.append(l)

			rey1 = int(100.0 * float(depth)) / 100.0;
			rey2 = int(100.0 * float(depthB)) / 100.0;
			info = holeA + " " + str(coreA) + " " + str(rey2) + "\t [TieTo] Log " + str(rey1)
			self.parent.AddTieInfo(info, rey2)

		if len(self.LogTieData) > 0 : 
			self.PreviewFirstNo = 1
			self.PreviewNumTies = 1


	def SetSpliceFromFile(self, tie_list, flag):
		# clean splice core
		self.SpliceCore = []
		self.SplicedHole = []
		if flag == False :
			self.SpliceTieData = []
			self.RealSpliceTie = []

		index = 0
		prevCoreIndex = -1 
		prevDepth = 0.0
		self.maxSPcore = 0

		l = []
		l.append((-1, -1, -1, -1, -1, -1, -1, -1, -1))
		id = -1
		idback = -1 
		strtypeA = ""
		strtypeB = ""
		for tie_data in tie_list : 
			id, typeB, holeB, coreB, typeA, holeA, coreA, depthA, depthB = tie_data 
			if typeA == 'GRA' :
				typeA = 'Bulk Density(GRA)'
			if typeB == 'GRA' :
				typeB = 'Bulk Density(GRA)'

			if flag == False :
				self.RealSpliceTie.append(l)
				self.RealSpliceTie.append(l)
			if idback != -1 and id == -1 :
				self.SpliceCore.append(coreidB)

			coreidA = 0
			coreidB = 0
			count = 0
			start = False
			for data in self.DrawData["CoreInfo"]:
				for r in data:
					#if r[0] == 0 : 
					#	start = True
					#if start == True :
						if r[3] == holeA and r[4] == str(coreA) and r[10] == typeA :
							coreidA = int(r[0])
							count = count + 1
						if r[3] == holeB and r[4] == str(coreB) and r[10] == typeB :
							coreidB = int(r[0])
							count = count + 1
						if count == 2:
							break
				if count == 2:
					break

			if prevCoreIndex != coreidA :
				self.SpliceCore.append(coreidA)
			prevCoreIndex = coreidA

			idback = id
			if id != -1 :
				if index == 0 : 
					self.GrabCore(coreidB, 1, -1, depthB)
					index = 1
				else : 
					if prevCoreIndex == coreidB : 
						self.GrabCore(coreidB, 3, prevDepth, depthB)
					else : 
						self.GrabCore(coreidB, 1, -1, depthB)

		if id != -1 :
			self.SpliceCore.append(coreidB)

		prevCoreIndex = coreidA
		self.PreviousSpliceCore = coreidB 
		prevDepth = depthB

		self.spliceCount = len(self.SpliceCore) 
		self.maxSPcore = self.spliceCount 
		self.SpliceTieFromFile = len(self.RealSpliceTie)

		if self.spliceCount >= 2 :
			if self.SpliceCore[0] == self.SpliceCore[1] :
				self.begin_append = True 


	def OnSetQTCb(self, event) :
		opId = event.GetId() 

		"""
		if opId == 1 : # register the core as bas core 
			for mouse in self.DrawData["MouseInfo"] :
				idx = mouse[0]
				for data in self.DrawData["CoreInfo"] :
					for info in data :
						if idx == info[0] :
							type = info[10]
							if type == "Natural Gamma" :
								type = "NaturalGamma"
							py_correlator.setCoreQuality(info[3], int(info[4]), 1, type)
							self.parent.dataFrame.OnUPDATE_CULLTABLE(type)
							self.parent.UpdateData()
							return	
				break
		elif opId == 2 : # register back it to good core
			for mouse in self.DrawData["MouseInfo"] :
				idx = mouse[0]
				for data in self.DrawData["CoreInfo"] :
					for info in data :
						if idx == info[0] :
							type = info[10]
							if type == "Natural Gamma" :
								type = "NaturalGamma"
							py_correlator.setCoreQuality(info[3], int(info[4]), 0, type)
							self.parent.dataFrame.OnUPDATE_CULLTABLE(type)
							self.parent.UpdateData()
							return	
				break
		elif opId == 3 : # show this core on Corelyzer 
		"""	
		if opId == 3 : # show this core on Corelyzer 
			for mouse in self.DrawData["MouseInfo"] :
				idx = mouse[0]
				for data in self.DrawData["CoreInfo"] :
					for info in data :
						if idx == info[0] :
							self.parent.ShowCoreSend(info[2], info[1], info[3], info[4])
		elif opId == 4 : 
			for mouse in self.DrawData["MouseInfo"] :
				idx = mouse[0]
				for data in self.DrawData["CoreInfo"] :
					for info in data :
						if idx == info[0] :
							return	
				break


	def OnScaleSelectionCb(self, event) :
		opId = event.GetId() 
		if opId == 1 : # scale up
			if self.bothscale == 0 :
				self.bothscale = 1 
			else :
				self.bothscale = 0 
		elif opId == 2 : # data scale down
			if self.datascale == 0 :
				self.datascale = 1 
			else :
				self.datascale = 0 
		self.UpdateDrawing()

	def OnLogTieSelectionCb(self, event) :
		opId = event.GetId() 
		self.activeSATie = -1
		self.showMenu = False
		if opId == 1 :
			self.DeleteLogTie()
			self.PreviewLog[0] = -1
			self.PreviewLog[1] = -1
			self.PreviewLog[2] = 1.0 
			self.PreviewLog[3] = 0
			self.PreviewLog[4] = -1
			self.PreviewLog[5] = -1
			self.PreviewLog[6] = 1.0 
			self.saganDepth = -1
		elif opId == 2 :
			self.MatchLog()

		self.LogselectedTie = -1
		self.drag = 0 
		self.UpdateDrawing()

	def DeleteLogTie(self) :
		if self.LogselectedTie >= 0 :
			tieNo = -1
			data = self.LogTieData[self.LogselectedTie]
			fixed = 0
			for r in data :
				fixed = r[3]
				tieNo = r[8]

			if tieNo > 0 :
				ret = py_correlator.delete_sagan(tieNo)
				if ret == 0 :
					self.LogselectedTie = -1
					return

				if fixed == 0 : # move tie
					#self.LogTieData.remove(data)
					#data = self.LogTieData[self.LogselectedTie-1]
					#self.LogTieData.remove(data)
					self.LogTieData.pop(self.LogselectedTie)
					self.LogTieData.pop(self.LogselectedTie - 1)
				else :		 # fixed tie 
					length = len(self.LogTieData)
					if (self.SPselectedTie + 1) < length :
						#data = self.LogTieData[self.LogselectedTie+1]
						#self.LogTieData.remove(data)
						self.LogTieData.pop(self.LogselectedTie + 1)
					#data = self.LogTieData[self.LogselectedTie]
					#self.LogTieData.remove(data)
					self.LogTieData.pop(self.LogselectedTie)
				#self.HoleData = []
				#self.parent.OnGetData(self.parent.smoothDisplay, True)

				if self.hole_sagan == -1 :
					self.parent.UpdateELD(True)
				else : 
					self.OnUpdateHoleELD()
				self.parent.EldChange = True


				s = "Log/Core Match undo: " + str(datetime.today()) + "\n\n"
				self.parent.logFileptr.write(s)
				if self.parent.showReportPanel == 1 :
					self.parent.OnUpdateReport()

				i = -1 
				if fixed == 1 :
					i = (self.LogselectedTie + 1) / 2
				else :
					i = self.LogselectedTie / 2
				self.parent.eldPanel.DeleteTie(i)

			else :
				self.OnClearTies(2)

			self.LogselectedTie = -1
			if self.parent.eldPanel.fileList.GetCount() == 0 :
				self.LogAutoMode = 1
				self.parent.autoPanel.OnButtonEnable(0, True)

	def MatchLog(self) :
		if self.lastLogTie != -1 :
			self.LogselectedTie = self.lastLogTie
			self.lastLogTie = -1

		if self.LogselectedTie >= 0 :
			tieNo = -1 
			data = self.LogTieData[self.LogselectedTie]
			coreidA = 0
			coreidB = 0
			depth = 0
			corexB = 0
			y1 = 0
			y2 = 0
			x1 = 0
			x2 = 0
			for r in data :
				coreidB = r[2]
				#y1 = (r[1] - self.startDepth) / ( self.length / self.gap ) + self.SPrulerStartDepth
				y1 = r[6]
				x1 = r[4]

			data = self.LogTieData[self.LogselectedTie - 1]
			for r in data :
				coreidA = r[2]
				depth = r[6]
				#y2 = (r[1] - self.startDepth) / ( self.length / self.gap ) + self.SPrulerStartDepth
				y2 = r[6]
				tieNo = r[8]
				x2 = r[4]

			reversed = False
			if x1 < x2 :
				reversed = True

			holeA = '-'
			holeB = '-'
			coreA = -1
			coreB = -1
			count = 0
			
			for s in self.DrawData["CoreInfo"]:
				data = s
				for r in data:
					if r[0] == coreidA :
						holeA = r[3]
						coreA = r[4]
						count = count + 1
					if r[0] == coreidB :
						holeB = r[3]
						coreB = r[4]
						count = count + 1
					if count >= 2:
						break
				if count >= 2 :
					break

			if holeA != '-' and holeB != '-' :
				preTieNo = tieNo
				annot_str = ""
				rd = -999
				if reversed == False :
					tieNo, annot_str, rd = py_correlator.sagan(holeB, int(coreB), y1, holeA, int(coreA), y2, tieNo)
				else :
					tieNo, annot_str, rd = py_correlator.sagan(holeA, int(coreA), y2, holeB, int(coreB), y1, tieNo)
					temp = y2
					y2 = y1
					y1 = temp

				self.parent.EldChange = True
				if tieNo == 0 :
					self.LogselectedTie = -1
					self.drag = 0
					#print "[DEBUG] tieNo is Zero -- then error"
					self.parent.OnShowMessage("Error", "Could not make tie", 1)
					return

				if self.PreviewNumTies == 0 :
					self.PreviewNumTies = 1

				self.saganDepth = -1
				self.PreviewLog[0] = -1 
				self.PreviewLog[1] = -1 
				self.PreviewLog[2] = 1.0 
				self.PreviewLog[3] = 0
				self.PreviewLog[4] = -1 
				self.PreviewLog[5] = -1 
				self.PreviewLog[6] = 1.0 
				if self.LogAutoMode == 1 :
					self.LogAutoMode = 0
					self.parent.autoPanel.OnButtonEnable(0, False)
		
				rey1 = int(100.0 * float(y1)) / 100.0;
				rey2 = int(100.0 * float(y2)) / 100.0;
				#info = str(holeA) + " " + str(coreA) + " " +str(rey2) + "\t [TieTo] Log " +str(rey1)
				info = annot_str + " " + str(rey2) + "\t [TieTo] Log " + str(rey1)
				if preTieNo != tieNo :
					self.parent.AddTieInfo(info, rey1)
				else :
					self.parent.UpdateTieInfo(info, rey1, self.LogselectedTie)

				s = "Log/Core Match: hole " + holeA + " core " + coreA + ": " + str(datetime.today()) + "\n"
				self.parent.logFileptr.write(s)
				s = holeA + " " + coreA + " " + str(y2) + " tied to " + holeB + " " + coreB + " " + str(y1) + "\n\n"
				self.parent.logFileptr.write(s)

				#self.SpliceData = []
				#self.HoleData = []
				#self.parent.OnGetData(self.parent.smoothDisplay, True)
				if self.hole_sagan == -1 :
					self.parent.UpdateELD(True)
				else : 
					self.OnUpdateHoleELD()

				if len(self.LogTieData) >= 2 :
					if reversed == False :
						data = self.LogTieData[self.LogselectedTie]
					else :
						data = self.LogTieData[self.LogselectedTie - 1]
					prevy = 0 
					prevd = 0 
					for r in data :
						x, y, n, f, startx, m, d, s, t, raw = r
						y = self.startDepth + (rd - self.SPrulerStartDepth) * (self.length / self.gap)
						d = rd 

						prevy = y 
						prevd = d 
						newtag = (x, y, n, f, startx, m, d, s, tieNo, raw)
						data.remove(r)
						data.insert(0, newtag)

					if reversed == False :
						data = self.LogTieData[self.LogselectedTie - 1]
					else :
						data = self.LogTieData[self.LogselectedTie]
					for r in data :
						x, y, n, f, startx, m, d, s, t, raw = r
						newtag = (x, prevy, n, f, startx, m, prevd, s, tieNo, raw)
						data.remove(r)
						data.insert(0, newtag)

					self.LogselectedTie = -1

	def OnUpdateHoleELD(self) :
		self.parent.UpdateCORE()
		self.parent.UpdateSMOOTH_CORE()
		self.parent.UpdateSaganTie()
		self.LogSpliceData = []
		icount = 0
		for data in self.HoleData:
			for r in data:
				if icount == self.hole_sagan :
					hole = r 
					l = []
					l.append(hole)
					self.LogSpliceData.append(l)
					break
			if self.LogSpliceData != [] :
				break
			icount += 1 
		icount = 0
		self.LogSpliceSmoothData = []
		for data in self.SmoothData:
			for r in data:
				if icount == self.hole_sagan :
					hole = r 
					l = []
					l.append(hole)
					self.LogSpliceSmoothData.append(l)
					break
			if self.LogSpliceSmoothData != [] :
				break
			icount += 1 

	def OnSortList(self, index) :
		data = self.LogTieData[self.LogselectedTie]
		data1 = self.LogTieData[self.LogselectedTie - 1]
		self.LogTieData.remove(data)
		self.LogTieData.remove(data1)
		self.LogTieData.insert(index - 1, data)
		self.LogTieData.insert(index - 1, data1)
		self.LogselectedTie = index 

	# 8/28/2013 brg: Better name?
	def ApplySplice(self, tieIndex) :
		if tieIndex >= 0:
			tieNo = 0
			coreidA = coreidB = 0
			depth = 0
			corexB = 0
			x1 = x2 = y1 = y2 = 0
			
			# 8/28/2013 brg: Previously for-looped through a list of tie tuples. Since we're just assigning,
			# use the last tuple and be done with it.
			dataA = self.SpliceTieData[tieIndex]
			dataATuple = dataA[-1]

			coreidB = dataATuple[2]
			y1 = dataATuple[6]
			x1 = dataATuple[4]

			dataB = self.SpliceTieData[tieIndex - 1]
			dataBTuple = dataB[-1]
			coreidA = dataBTuple[2]
			depth = dataBTuple[6]
			y2 = dataBTuple[6]
			tieNo = dataBTuple[8]
			x2 = dataBTuple[4]

			reversed = False 
			if x2 > x1 :
				reversed = True

			holeA = holeB = '-'
			coreA = coreB = -1
			typeA = typeB = ''
			count = 0
			for s in self.DrawData["CoreInfo"]:
				data = s
				for r in data:
					if r[0] == coreidA :
						holeA = r[3]
						coreA = r[4]
						typeA = r[10]
						count = count + 1
					if r[0] == coreidB :
						holeB = r[3]
						coreB = r[4]
						typeB = r[10]
						count = count + 1
					if count >= 2:
						break
				if count >= 2 :
					break

			type_a = self.GetTypeID(typeA)
			type_b = self.GetTypeID(typeB)
			if type_a != type_b :
				self.multipleType = True 

			if holeA != '-' and holeB != '-' :
				if reversed == False :
					splice_data = py_correlator.splice(typeB, holeB, int(coreB), y1, typeA, holeA, int(coreA), y2, tieNo, self.parent.smoothDisplay, 0)
				else :
					splice_data = py_correlator.splice(typeA, holeA, int(coreA), y2, typeB, holeB, int(coreB), y1, tieNo, self.parent.smoothDisplay, 0)
				self.parent.SpliceChange = True
				py_correlator.saveAttributeFile(self.parent.CurrentDir + 'tmp.splice.table'  , 2)

				if tieNo <= 0 and splice_data[0] > 0 : 
					self.spliceCount = self.spliceCount + 1
					self.RealSpliceTie.append(dataB)
					self.RealSpliceTie.append(dataA)
				if splice_data[0] == -1 : 
					self.parent.OnShowMessage("Error", "It can not find value point.", 1)
					self.parent.splicePanel.OnButtonEnable(0, True)
					self.parent.splicePanel.OnButtonEnable(1, False)
					return

				data = self.SpliceTieData[tieIndex]
				for rtie in data :
					x, y, n, f, startx, m, d, splicex, i, mode = rtie
					data.remove(rtie)
					if mode == 1 :
						d = splice_data[2]
					news = (x, y, n, f, startx, m, d, splicex, splice_data[0], mode)
					data.insert(0, news)
				data = self.SpliceTieData[tieIndex - 1]
				for rtie in data : 
					x, y, n, f, startx, m, d, splicex, i, mode = rtie
					data.remove(rtie)
					if mode == 1 :
						d = splice_data[2]
					news = (x, y, n, f, startx, m, d, splicex, splice_data[0], mode)
					data.insert(0, news)

				if splice_data[1] != "" :
					self.SpliceData = []
					self.parent.filterPanel.OnLock()
					self.parent.ParseData(splice_data[1], self.SpliceData)
					self.parent.filterPanel.OnRelease()
					self.parent.UpdateSMOOTH_SPLICE(False)

					# brg 8/28/2013: Necessary? Logic in button splice, not right-click splice.
					# Still don't understand why there'd be any difference at all.
					self.parent.splicePanel.OnButtonEnable(0, False)
					self.parent.splicePanel.OnButtonEnable(1, True)

					s = "Constrained Splice: "	
					if self.Constrained == 0 :
						s = "Unconstrained Splice: "	
						
					s = s + "hole " + holeB + " core " + coreB + ": " + str(datetime.today()) + "\n"
					self.parent.logFileptr.write(s)
					s = holeA + " " + coreA + " " + str(y1) + " tied to " + holeB + " " + coreB + " " + str(y2) + "\n\n"
					self.parent.logFileptr.write(s)

					self.parent.SpliceSectionSend(holeA, coreA, y1, "split", tieNo)
					self.parent.SpliceSectionSend(holeB, coreB, y2, None, tieNo)
					if tieNo > 0 :
						self.parent.SpliceSectionSend(holeA, coreA, y1, "split", -1)
						self.parent.SpliceSectionSend(holeB, coreB, y2, None, -1)

					self.SpliceTieData = []
					self.SpliceTieData.append(dataB)
					self.SpliceTieData.append(dataA)

		self.SPselectedTie = -1
		self.SPGuideCore = []
		self.drag = 0 
		self.UpdateDrawing()


	def OnSpliceTieSelectionCb(self, event) :
		opId = event.GetId() 
		self.activeSPTie = -1
		self.showMenu = False
		if opId == 1 :
			if len(self.SpliceTieData) > 2 :
				if self.SPselectedTie < 2 :
					self.OnUndoSplice()
				else :
					self.OnClearTies(1)
			else :
				if self.SpliceTieFromFile != len(self.RealSpliceTie) :
					self.OnUndoSplice()
				else :
					self.OnClearTies(1)
			self.SPselectedTie = -1
			self.SPGuideCore = []
			self.drag = 0 
			self.UpdateDrawing()
		elif opId == 2 :
			self.ApplySplice(self.SPselectedTie)

	def OnClearTies(self, mode) :
		if mode == 0 :
			self.TieData = []
			self.GuideCore = []
			self.selectedTie = -1
			self.parent.clearSend()
		elif mode == 1 :
			realties = len(self.RealSpliceTie)
			curties = len(self.SpliceTieData)
			if realties == 0 and curties <= 2 :
				self.SpliceTieData = []
			if realties >= 2 and curties <= 4:
				self.SpliceTieData = []
				realties = realties - 2
				data = self.RealSpliceTie[realties]
				self.SpliceTieData.append(data)
				realties = realties + 1 
				data = self.RealSpliceTie[realties]
				self.SpliceTieData.append(data)

			self.SPGuideCore = []
			self.SPselectedTie = -1
		elif mode == 2 :
			last = self.LogselectedTie + 1
			#last = self.LDselectedTie + 1
			length = last % 2
			if length == 0 and last != 0 :
				self.LogTieData.pop(last - 1)	
				self.LogTieData.pop(last - 2)	
			elif length == 1 and len(self.LogTieData) != 0 : 
				self.LogTieData.pop(last - 1)	

			self.PreviewLog[0] = -1
			self.PreviewLog[1] = -1
			self.PreviewLog[2] = 1.0 
			self.PreviewLog[3] = 0
			self.PreviewLog[4] = -1
			self.PreviewLog[5] = -1
			self.PreviewLog[6] = 1.0 
			self.saganDepth = -1
			self.LogselectedTie = -1
			self.LDselectedTie = -1

		self.drag = 0 
		self.UpdateDrawing()

	def MakeStraightLie(self) :
		last = len(self.LogTieData) 
		length = last % 2
		if length == 0 and last != 0 :
			data = self.LogTieData[last - 2]	
			prevy = 0
			prevd = 0
			for r in data :
				x, y, n, f, startx, m, d, s, t, raw = r
				prevy = y
				prevd = d
			data = self.LogTieData[last - 1]	
			for r in data :
				x, y, n, f, startx, m, d, s, t, raw = r
				newtag = (x, prevy, n, f, startx, m, prevd, s, t, raw)
				data.remove(r)
				data.insert(0, newtag)

			self.UpdateDrawing()


	def OnTieSelectionCb(self, event) :
		opId = event.GetId() 
		self.activeTie = -1
		self.showMenu = False
		if opId == 1 :
			fixed = 0
			if self.selectedTie >= 0 :
				data = self.TieData[self.selectedTie]
				for r in data :
					x, y, n, fixed, startx, m, d = r
			if fixed == 0 : # move tie
				self.TieData.remove(data)
				data = self.TieData[self.selectedTie - 1]
				self.TieData.remove(data)
			else :		 # fixed tie 
				length = len(self.TieData)
				if (self.selectedTie + 1) < length :
					data = self.TieData[self.selectedTie + 1]
					self.TieData.remove(data)
				data = self.TieData[self.selectedTie]
				self.TieData.remove(data)
			self.GuideCore = []
			self.parent.clearSend()
		elif opId == 4:
			py_correlator.undo(1, "X", 0)
			self.parent.AffineChange = True
			py_correlator.saveAttributeFile(self.parent.CurrentDir + 'tmp.affine.table'  , 1)

			s = "Composite undo previous offset: " + str(datetime.today()) + "\n\n"
			self.parent.logFileptr.write(s)
			if self.parent.showReportPanel == 1 :
				self.parent.OnUpdateReport()

			self.AdjustDepthCore = []
			self.parent.UpdateSend()
			#self.parent.UndoShiftSectionSend()
			self.parent.UpdateData()
			self.parent.UpdateStratData()
			self.parent.compositePanel.OnButtonEnable(1, False)
		elif opId == 5:
			if self.selectedTie >= 0 :
				data = self.TieData[self.selectedTie]
				coreId = 0
				for r in data :
					x, y, n, fixed, startx, m, d = r
					coreId = n
				holeA = '-'
				coreA = -1
				count = 0
				for s in self.DrawData["CoreInfo"]:
					data = s
					for r in data:
						if r[0] == coreId :
						 holeA = r[3]
						 coreA = r[4]
						 count = count + 1
						if count >= 1:
						 break
					if count >= 1 :
						 break

				#print "[DEBUG] " + holeA + " " + str(coreA) + " undo "
				if holeA != '-' :
					py_correlator.undo(2, holeA, int(coreA))

					self.parent.AffineChange = True
					py_correlator.saveAttributeFile(self.parent.CurrentDir + 'tmp.affine.table'  , 1)
					self.parent.UpdateSend()

					s = "Composite undo offsets the core above: hole " + holeA + " core " + coreA + ": " + str(datetime.today()) + "\n\n" 
					self.parent.logFileptr.write(s)

					self.AdjustDepthCore = []
					self.parent.UpdateData()
					self.parent.UpdateStratData()
					self.parent.compositePanel.OnButtonEnable(1, False)
		elif opId == 3 or opId == 2:
			if self.selectedTie >= 0 :
				data_move = self.TieData[self.selectedTie]
				y1 = 0
				y2 = 0
				coreId = 0
				for r in data_move :
					x, y, n, fixed, startx, m, d = r
					mouseY = y
					y1 = (y - self.startDepth) / (self.length / self.gap) + self.rulerStartDepth
					coreId = n
				self.AdjustDepthCore.append(coreId)
				data_fix = self.TieData[self.selectedTie - 1]
				for r in data_fix :
					x, y, n, fixed, startx, m, d = r
					currentY = y
					y2 = (y - self.startDepth) / (self.length / self.gap) + self.rulerStartDepth
					data_fix.remove(r)
				shift = y2 - y1
				self.OnDataChange(coreId, shift)

				holeA = '-' 
				holeB = '-' 
				coreA = -1 
				coreB = -1 
				count = 0
				leg = " "
				site = " "
				data_type = "-"

				for s in self.DrawData["CoreInfo"]:
					data = s
					for r in data:
						if r[0] == coreId :
							data_type = r[10] 
							holeA = r[3] 
							coreA = r[4] 
							leg = r[2]
							site = r[1]
							count = count + 1 
						if r[0] == n :
							holeB = r[3] 
							coreB = r[4] 
							count = count + 1 
							if count >= 2:
								break
					if count >= 2 : 
						break


				if holeA != '-' and holeB != '-' : 
					#print "[DEBUG] Compostie " + str(y1) +  " " + str(y2)
					coef = py_correlator.composite(holeA, int(coreA), y1, holeB, int(coreB), y2, opId, data_type)
					self.parent.AffineChange = True
					self.parent.UpdateData()
					self.parent.UpdateStratData()

					self.TieData = []
					self.parent.compositePanel.OnButtonEnable(0, False)
					self.parent.compositePanel.OnButtonEnable(1, True)
					self.parent.compositePanel.UpdateGrowthPlot()

					if opId == 3 : 
						s = "Composite(All Below): hole " + holeA + " core " + coreA + ": " + str(datetime.today()) + "\n"
						self.parent.logFileptr.write(s)
					else :
						s = "Composite: hole " + holeA + " core " + coreA + ": " + str(datetime.today()) + "\n"
						self.parent.logFileptr.write(s)

					s = holeA + " " + coreA + " " + str(y1) + " tied to " + holeB + " " + coreB + " " + str(y2) + "\n\n"
					self.parent.logFileptr.write(s)

					#self.parent.ShiftSectionSend(holeA, coreA, shift, opId)
					#ret = self.parent.FineTuneSend(leg, site, holeA, coreA, holeB, coreB, y2)
					#if ret != 0.0 :
					#	print "[DEBUG] Need to shift more : " + str(ret)
					#	coef = py_correlator.composite(holeA, int(coreA), y1, holeB, int(coreB), y1+ret, opId, data_type)

					#	if opId == 3 :
					#		s = "Composite(Fine Tune/All Below): hole " + holeA + " core " + coreA + ": " + str(datetime.today()) + "\n"
					#		self.parent.logFileptr.write(s)
					#	else :
					#		s = "Composite(Fine Tune): hole " + holeA + " core " + coreA + ": " + str(datetime.today()) + "\n"
					#		self.parent.logFileptr.write(s)
					#	s = holeA + " " + coreA + " " + str(y1) + " tied to " + holeB + " " + coreB + " " + str(y1+ret) + "\n\n"
					#	self.parent.logFileptr.write(s)


					#	self.parent.UpdateData()
					#	if opId == 3 :
					#		self.parent.ShiftSectionSend(holeA, coreA, ret, opId)

					py_correlator.saveAttributeFile(self.parent.CurrentDir + 'tmp.affine.table'  , 1)
					self.parent.ShiftSectionSend(holeA, coreA, shift, opId)

					if self.parent.showReportPanel == 1 :
						self.parent.OnUpdateReport()

			self.GuideCore = []

		self.selectedTie = -1
		self.drag = 0 
		self.UpdateDrawing()

	def OnAdjustCore(self, opt, actionType, strOffset):
		self.parent.compositePanel.OnButtonEnable(0, False)
		self.parent.compositePanel.OnButtonEnable(1, True)
		offset = float(strOffset)
		if self.selectedLastTie < 0 :
			self.selectedLastTie = len(self.TieData) - 1

		if self.selectedLastTie >= 0 :
			data_move = self.TieData[self.selectedLastTie]
			y1 = 0
			y2 = 0
			coreId = 0
			for r in data_move :
				x, y, n, fixed, startx, m, d = r
				mouseY = y
				y1 = (y - self.startDepth) / (self.length / self.gap) + self.rulerStartDepth
				coreId = n
			self.AdjustDepthCore.append(coreId)
			data_fix = self.TieData[self.selectedLastTie - 1]
			for r in data_fix :
				x, y, n, fixed, startx, m, d = r
				currentY = y
				y2 = (y - self.startDepth) / (self.length / self.gap) + self.rulerStartDepth
				data_fix.remove(r)
			shift = y2 - y1
			if actionType == 0 : # to best 
				y1 = y1 + offset
				shift = shift + offset 
			elif actionType == 2 : # to given
				# ERROR - HYEJUNG
				y1 = y2 - offset
				shift = offset 

			self.OnDataChange(coreId, shift)

			holeA = '-'
			holeB = '-'
			coreA = -1
			coreB = -1
			count = 0
			leg = " " 
			site = " " 
			data_type = "-" 

			for s in self.DrawData["CoreInfo"]:
				data = s
				for r in data:
					if r[0] == coreId :
						data_type = r[10] 
						holeA = r[3]
						coreA = r[4]
						leg = r[2]
						site = r[1]
						count = count + 1
					if r[0] == n :
						holeB = r[3]
						coreB = r[4]
						count = count + 1
					if count >= 2:
						break
				if count >= 2 :
					break

			if holeA != '-' and holeB != '-' :
				# actionType(0=best, 1=tie, 2=given), strOffset 
				opId = 2
				#print "[DEBUG] Compostie " + str(y1) +  " " + str(y2)
				if actionType < 2 : 
					if opt == 0 :
						opId = 2
						coef = py_correlator.composite(holeA, int(coreA), y1, holeB, int(coreB), y2, 2, data_type)
					else :
						opId = 3 
						coef = py_correlator.composite(holeA, int(coreA), y1, holeB, int(coreB), y2, 3, data_type)
				else :
					if opt == 0 :
						coef = py_correlator.composite(holeA, int(coreA), y1, holeB, int(coreB), shift, 4, data_type)
					else :
						coef = py_correlator.composite(holeA, int(coreA), y1, holeB, int(coreB), shift, 5, data_type)

				self.parent.AffineChange = True

				if opt == 0 :
					s = "Composite: hole " + holeA + " core " + coreA + ": " + str(datetime.today()) + "\n"
					self.parent.logFileptr.write(s)
				else :
					s = "Composite(All Below): hole " + holeA + " core " + coreA + ": " + str(datetime.today()) + "\n"
					self.parent.logFileptr.write(s)

				s = holeA + " " + coreA + " " + str(y1) + " tied to " + holeB + " " + coreB + " " + str(y2) + "\n\n"
				self.parent.logFileptr.write(s)

				#self.parent.ShiftSectionSend(holeA, coreA, shift, opId)
				#ret = self.parent.FineTuneSend(leg, site, holeA, coreA, holeB, coreB, y2)
				#if ret != 0.0 :
				#	print "[DEBUG] Need to shift more : " + str(ret)
				#	#opId = 2
				#	coef = py_correlator.composite(holeA, int(coreA), y1, holeB, int(coreB), y1+ret, opId, data_type)
				#	if opt == 0 :
				#		s = "Composite(Fine Tune): hole " + holeB + " core " + coreB + ": " + str(datetime.today()) + "\n"
				#		self.parent.logFileptr.write(s)
				#	else :
				#		s = "Composite(Fine Tune/All Below): hole " + holeB + " core " + coreB + ": " + str(datetime.today()) + "\n"
				#		self.parent.logFileptr.write(s)
				#	s = holeA + " " + coreA + " " + str(y1) + " tied to " + holeB + " " + coreB + " " + str(y1+ ret) + "\n\n"
				#	self.parent.logFileptr.write(s)
				#	if opId == 3 :
				#		self.parent.ShiftSectionSend(holeA, coreA, ret, opId)				
				py_correlator.saveAttributeFile(self.parent.CurrentDir + 'tmp.affine.table'  , 1)
				self.parent.ShiftSectionSend(holeA, coreA, shift, opId)

				if self.parent.showReportPanel == 1 :
					self.parent.OnUpdateReport()

				self.parent.UpdateData()
				self.parent.UpdateStratData()
				self.TieData = []

			self.selectedTie = -1
			self.GuideCore = []
			self.drag = 0 
			self.UpdateDrawing()


	def OnUndoCore(self, opt):
		self.parent.compositePanel.OnButtonEnable(1, False)
		if opt == 0 :
			py_correlator.undo(1, "X", 0)
			self.parent.AffineChange = True
			py_correlator.saveAttributeFile(self.parent.CurrentDir + 'tmp.affine.table'  , 1)

			s = "Composite undo previous offset: " + str(datetime.today()) + "\n\n"
			self.parent.logFileptr.write(s)
			#self.parent.UndoShiftSectionSend()
			self.parent.UpdateSend()
			self.parent.UpdateData()
			self.parent.UpdateStratData()
		else :
			if self.selectedLastTie < 0 :
				self.selectedLastTie = len(self.TieData) - 1
			if self.selectedLastTie >= 0 and self.selectedLastTie < len(self.TieData):
				data = self.TieData[self.selectedLastTie]
				coreId = 0
				for r in data :
					x, y, n, fixed, startx, m, d = r
					coreId = n
				holeA = '-'
				coreA = -1
				count = 0
				for s in self.DrawData["CoreInfo"]:
					data = s
					for r in data:
						if r[0] == coreId :
						 holeA = r[3]
						 coreA = r[4]
						 count = count + 1
						if count >= 1:
						 break
					if count >= 1 :
						 break

				#print "[DEBUG] " + holeA + " " + str(coreA) + " undo "
				if holeA != '-' :
					py_correlator.undo(2, holeA, int(coreA))

					self.parent.AffineChange = True
					py_correlator.saveAttributeFile(self.parent.CurrentDir + 'tmp.affine.table'  , 1)

					s = "Composite undo offsets the core above: hole " + holeA + " core " + coreA + ": " + str(datetime.today()) + "\n\n"
					self.parent.logFileptr.write(s)
					self.parent.UpdateData()
					self.parent.UpdateStratData()
					self.parent.UpdateSend()

		self.AdjustDepthCore = []
		self.parent.UpdateData()

	def GetTypeID(self, typeA):
		type = -1
		if typeA == "Susceptibility" :
			type = 32
		elif typeA == "Natural Gamma" :
			type = 33
		elif typeA == "Reflectance" :
			type = 34
		elif typeA == "Other Type" :
			type = 35
		elif typeA == "ODP Other1" :
			type = 7 
		elif typeA == "ODP Other2" :
			type = 8 
		elif typeA == "ODP Other3" :
			type = 9 
		elif typeA == "ODP Other4" :
			type = 10 
		elif typeA == "ODP Other5" :
			type = 11
		elif typeA == "Bulk Density(GRA)" :
			type = 30
		elif typeA == "Pwave" :
			type = 31
		return type
		
	def GetSpliceCore(self):
		lastTie = len(self.SpliceCore) - 1 
		if lastTie >= 0 :
			lastCore = self.SpliceCore[lastTie]
			for s in self.DrawData["CoreInfo"]:
				data = s
				for r in data:
					if r[0] == lastCore :
	 					hole = r[3]
	 					core = r[4]
	 					type = r[10]
	 					l = hole, core, type
						return l 

		return None

	def OnSpliceCore(self):
		self.parent.splicePanel.OnButtonEnable(0, False)
		self.parent.splicePanel.OnButtonEnable(1, True)
		lastTie = len(self.SpliceTieData) - 1
		# print "[DEBUG] length of Splice Ties " + str(len(self.SpliceTieData)) 
		self.ApplySplice(lastTie)

	def OnUndoSplice(self):
		lastTie = len(self.RealSpliceTie) - 1
	
		if lastTie >= 0 :
			tieNo = -2
			data = self.RealSpliceTie[lastTie]
			fixed = 0
			for r in data :
				fixed = r[3]
				tieNo = r[8]

			if tieNo == -1 :
				self.RealSpliceTie.pop()
				self.RealSpliceTie.pop()
				#self.RealSpliceTie.remove(data)
				#data = self.RealSpliceTie[lastTie-1]
				#self.RealSpliceTie.remove(data)
				tieNo = 0
			elif tieNo >= 0  :
				if fixed == 0 : # move tie
					self.RealSpliceTie.pop()
					self.RealSpliceTie.pop()
					#self.RealSpliceTie.remove(data)
					#data = self.RealSpliceTie[lastTie-1]
					#self.RealSpliceTie.remove(data)
				else :		 # fixed tie
					#length = len(self.SpliceTieData)
					#if (self.SPselectedTie+1) < length :
					#	data = self.RealSpliceTie[lastTie+1]
					#	self.RealSpliceTie.remove(data)
					#data = self.RealSpliceTie[lastTie]
					#self.RealSpliceTie.remove(data)
					self.RealSpliceTie.pop()
					self.RealSpliceTie.pop()

			# delete splice tie
			if tieNo >= 0 :
				splice_data = py_correlator.delete_splice(tieNo, self.parent.smoothDisplay)
				py_correlator.saveAttributeFile(self.parent.CurrentDir + 'tmp.splice.table'  , 2)
				self.parent.SpliceChange = True
				self.spliceCount = self.spliceCount - 1
				if splice_data != "" :
					self.SpliceData = []
					self.parent.filterPanel.OnLock()
					self.parent.ParseData(splice_data, self.SpliceData)

					self.parent.filterPanel.OnRelease()
					self.parent.UpdateSMOOTH_SPLICE(False)
					if self.SpliceData == [] : 
						self.parent.splicePanel.OnButtonEnable(4, False)

					#if self.SmoothData != [] :
					#	splice_data = py_correlator.getData(4)
					#	if splice_data != "" :
					#		self.SpliceSmoothData = []
					#		self.parent.filterPanel.OnLock()
					#		self.parent.ParseData(splice_data, self.SpliceSmoothData)
					#		self.parent.filterPanel.OnRelease()
					self.parent.UndoSpliceSectionSend()

				s = "Splice undo last spliced tie: " + str(datetime.today()) + "\n\n"
				self.parent.logFileptr.write(s)
				if self.parent.showReportPanel == 1 :
					 self.parent.OnUpdateReport()

				self.SPGuideCore = []
				self.SPselectedTie = -1
				
		if len(self.RealSpliceTie) == 0 :
			self.parent.splicePanel.OnButtonEnable(1, False)
			self.PreviousSpliceCore = self.SpliceCore[0] 
			self.CurrentSpliceCore = -1 

		self.SpliceTieData = []
		if len(self.RealSpliceTie) >= 2 :
			realties = len(self.RealSpliceTie) - 2
			data = self.RealSpliceTie[realties]
			for r in data :
				if r[2] >= 0 : 
					self.PreviousSpliceCore = r[2]
					self.PreviousSpliceCore = self.CurrentSpliceCore
					self.SpliceTieData.append(data)
					realties = realties + 1
					data = self.RealSpliceTie[realties]
					for r in data :
						self.CurrentSpliceCore = r[2]
					self.SpliceTieData.append(data)
				else :
					coresize = len(self.SpliceCore) - 2
					self.PreviousSpliceCore = self.SpliceCore[coresize] 
					self.CurrentSpliceCore = -1
					#self.parent.splicePanel.OnButtonEnable(1, False)

		#diffcore = len(self.SpliceCore) - len(self.RealSpliceTie)
		#self.SpliceCore.pop()
		#if diffcore > 1 and len(self.SpliceCore) > 1:
		#	self.SpliceCore.pop()

		ret = py_correlator.getData(2)
		if ret != "" :
			self.parent.ParseSpliceData(ret, True)
			ret = "" 

		self.spliceCount = len(self.SpliceCore)

		self.UpdateDrawing()

	def OnMouseWheel(self, event):
		if self.MainViewMode == True :
			self.OnMainMouseWheel(event)
		else :
			self.OnAgeDepthMouseWheel(event)

	def OnAgeDepthMouseWheel(self, event):
		pass

	def OnMainMouseWheel(self, event):
		rot = event.GetWheelRotation() 
		pos = event.GetPositionTuple()

		if pos[0] <= self.splicerX or self.isSecondScroll == 0:
			if self.parent.ScrollMax > 0 :
				if rot < 0 :
					self.rulerStartDepth += self.rulerTickRate
					if self.isSecondScroll == 0 : 
						self.SPrulerStartDepth = self.rulerStartDepth 
				else : 
					self.rulerStartDepth -= self.rulerTickRate
					if self.rulerStartDepth < 0 :
						self.rulerStartDepth = 0.0
					if self.isSecondScroll == 0 : 
						self.SPrulerStartDepth = self.rulerStartDepth 
				self.UpdateScroll(1)
		else :
			if self.isSecondScroll == 1 and self.parent.ScrollMax > 0 : 
				if rot < 0 :
					self.SPrulerStartDepth += self.rulerTickRate
				else : 
					self.SPrulerStartDepth -= self.rulerTickRate
					if self.SPrulerStartDepth < 0 :
						self.SPrulerStartDepth = 0.0
			self.UpdateScroll(2)

		self.UpdateDrawing()
		#event.Skip()


	def UpdateScroll(self, scroll_flag):
		if scroll_flag == 1 :
			rate = self.rulerStartDepth / self.parent.ScrollMax 
		elif scroll_flag == 2 :
			rate = self.SPrulerStartDepth / self.parent.ScrollMax 

		scroll_start = self.startDepth * 0.7	 
		scroll_width = self.Height - (self.startDepth * 1.6)
		scroll_width = scroll_width - scroll_start
		scroll_y = rate * scroll_width 
		scroll_width += scroll_start
		scroll_y += scroll_start
		if scroll_y < scroll_start :
			scroll_y = scroll_start
		if scroll_y > scroll_width :
			scroll_y = scroll_width 

		if scroll_flag == 1 :
			for key, data in self.DrawData.items():
				if key == "MovableInterface":
					bmp, x, y = data
					self.DrawData["MovableInterface"] = (bmp, x, scroll_y)

			if self.spliceWindowOn == 1 :
				bmp, x, y = self.DrawData["MovableSkin"]
				self.DrawData["MovableSkin"] = (bmp, x, scroll_y)

			if self.parent.client != None :
#				# self.parent.client.send("show_depth_range\t"+str(self.rulerStartDepth)+"\t"+str(self.rulerEndDepth)+"\n") # JULIAN
				_depth = (self.rulerStartDepth + self.rulerEndDepth) / 2.0
				self.parent.client.send("jump_to_depth\t" + str(_depth) + "\n")

		if self.isSecondScroll == 0 : # if composite/splice windows scroll together, scroll splice too
			scroll_flag = 2

		# brgtodo 4/23/2014: MovableInterface/Skin and Interface/Skin appear to be duplicating
		# most of their behavior/logic. Refactor into a common object.
		if scroll_flag == 2 :
			bmp, x, y = self.DrawData["Interface"]
			self.DrawData["Interface"] = (bmp, x, scroll_y)

			bmp, x, y = self.DrawData["Skin"]
			self.DrawData["Skin"] = (bmp, x, scroll_y)

	def OnCharUp(self, event):
		keyid = event.GetKeyCode()

		if keyid == wx.WXK_ALT :
			self.showGrid = False 
			self.UpdateDrawing()
		elif keyid == wx.WXK_SHIFT :
			self.pressedkeyShift = 0 
			self.UpdateDrawing()
		elif keyid == ord("D") :
			self.pressedkeyD = 0 
			self.UpdateDrawing()
		elif keyid == ord("S") :
			self.pressedkeyS = 0 
			self.UpdateDrawing()

	def OnChar(self, event):
		keyid = event.GetKeyCode()

		#if keyid == 27 :
		#	self.parent.OnExitButton(1)
		if keyid == 127 :
			self.TieData = [] 
			self.GuideCore = []
			self.UpdateDrawing()
		elif keyid == 72 :
			if self.hideTie == 1 :
				self.hideTie = 0
			else : 
				self.hideTie = 1
			self.UpdateDrawing()
		elif keyid == ord("D") :
			self.pressedkeyD = 1 
			self.UpdateDrawing()
		elif keyid == ord("S") :
			self.pressedkeyS = 1 
			self.UpdateDrawing()
		elif keyid == wx.WXK_ALT :
			self.showGrid = True
			self.UpdateDrawing()
		elif keyid == wx.WXK_SHIFT :
			self.pressedkeyShift = 1 
			self.UpdateDrawing()
		elif keyid == wx.WXK_DOWN and self.parent.ScrollMax > 0 :
			if self.activeTie == -1 and self.activeSPTie == -1 and self.activeSATie == -1:
				if self.isSecondScroll == 0:
					self.rulerStartDepth += self.rulerTickRate
					if self.rulerStartDepth > self.parent.ScrollMax :
						self.rulerStartDepth = self.parent.ScrollMax
					self.SPrulerStartDepth = self.rulerStartDepth 
				elif event.GetModifiers() & wx.MOD_SHIFT: # arrow + shift moves splice only
					self.SPrulerStartDepth += self.rulerTickRate
				else:
					self.rulerStartDepth += self.rulerTickRate
					if self.rulerStartDepth > self.parent.ScrollMax :
						self.rulerStartDepth = self.parent.ScrollMax

				self.UpdateScroll(1)
			else :
				self.UPDATE_TIE(False)
			self.UpdateDrawing()
		elif keyid == wx.WXK_UP and self.parent.ScrollMax > 0 :
			if self.activeTie == -1 and self.activeSPTie == -1 and self.activeSATie == -1:
				if self.isSecondScroll == 0:
					self.rulerStartDepth -= self.rulerTickRate
					if self.rulerStartDepth < 0 :
						self.rulerStartDepth = 0.0
					self.SPrulerStartDepth = self.rulerStartDepth
				elif event.GetModifiers() & wx.MOD_SHIFT: # arrow + shift moves splice only
					self.SPrulerStartDepth -= self.rulerTickRate
				else:
					self.rulerStartDepth -= self.rulerTickRate
					if self.rulerStartDepth < 0:
						self.rulerStartDepth = 0
					 
				self.UpdateScroll(1)
			else :
				self.UPDATE_TIE(True)
			self.UpdateDrawing()
		elif keyid == wx.WXK_LEFT :
			self.minScrollRange = self.minScrollRange - 15 
			if self.minScrollRange < 0 :
				self.minScrollRange = 0
			self.UpdateDrawing()
		elif keyid == wx.WXK_RIGHT :
			self.minScrollRange = self.minScrollRange + 15 
			if self.minScrollRange > self.parent.HScrollMax :
				self.minScrollRange = self.parent.HScrollMax 
			self.UpdateDrawing()
		event.Skip()


	def UPDATE_TIE(self, upflag):
		shift_delta = self.shift_range 
		if upflag == True :
			shift_delta *= -1 

		data = []
		if self.activeTie != -1 : 
			if len(self.TieData) < self.activeTie :
				self.activeTie = -1
				return

			data = self.TieData[self.activeTie]
			x = 0
			depth = 0
			n = 0 
			for r in data :
				x, y, n, f, startx, m, d = r
				depth = d + shift_delta
				y = self.startDepth + (depth - self.rulerStartDepth) * (self.length / self.gap)
				newtag = (x, y, n, f, startx, m, depth)
				data.remove(r)
				data.insert(0, newtag)

			data = []
			data = self.TieData[self.activeTie - 1]
			x2 = 0
			depth2 = 0
			n2 = 0 
			for r in data :
				x2 = r[0] 
				depth2 = r[6] 
				n2 = r[2]

			holenoA = 'x'
			holenoB = 'x'
			corenoA = -1
			corenoB = -1
			typeA = ''
			typeB = ''
			count = 0
			leg = " "
			site = " "
			for s in self.DrawData["CoreInfo"]:
				data = s
				for r in data:
					if r[0] == n2 :
						holenoA = r[3]
						corenoA = r[4]
						typeA = r[10]
						leg = r[2]
						site = r[1]
						count = count + 1
					elif r[0] == n :
						holenoB = r[3]
						corenoB = r[4]
						typeB = r[10]
						count = count + 1
					if count >= 2:
						break
				if count >= 2:
					break
	
			shift = depth2 - depth 
			shiftx = x2 - x
			self.OnUpdateGuideData(self.activeCore, shiftx, shift)
			self.parent.OnUpdateDepth(shift)
			self.parent.TieUpdateSend(leg, site, holenoA, int(corenoA), holenoB, int(corenoB), depth, shift)

			flag = self.parent.showELDPanel | self.parent.showCompositePanel | self.parent.showSplicePanel
			if flag == 1 :
				testret = py_correlator.evalcoef(typeA, holenoA, int(corenoA), depth2, typeB, holenoB, int(corenoB), depth)
				if testret != "" :
					self.parent.OnAddFirstGraph(testret, depth2, depth)

				for data_item in self.range :
					if data_item[0] == "Natural Gamma" and typeA == "NaturalGamma" :
						typeA = "Natural Gamma"
					elif data_item[0] == "NaturalGamma" and typeA == "Natural Gamma" :
						typeA = "NaturalGamma"
					if data_item[0] != typeA and data_item[0] != "splice" and data_item[0] != "log" :
						testret = py_correlator.evalcoef(data_item[0], holenoA, int(corenoA), depth2, data_item[0], holenoB, int(corenoB), depth)
						if testret != "" :
							self.parent.OnAddGraph(testret, depth2, depth)

				self.parent.OnUpdateGraph()


		elif self.activeSPTie != -1 :
			if len(self.SpliceTieData) < self.activeSPTie :
				self.activeSPTie = -1
				return

			data = self.SpliceTieData[self.activeSPTie]
			x = 0
			depth = 0
			n1 = 0 
			y1 = 0.0
			for r in data :
				x, y, n, f, startx, m, d, splicex, i, mode = r
				n1 = n
				depth = d + shift_delta
				y = self.startDepth + (depth - self.SPrulerStartDepth) * (self.length / self.gap)
				y1 = y
				newtag = (x, y, n, f, startx, m, depth, splicex, i, mode)
				data.remove(r)
				data.insert(0, newtag)


			data = self.SpliceTieData[self.activeSPTie - 1]
			x2 = 0
			depth2 = 0
			n2 = 0 
			for r in data :
				x, y, n, f, startx, m, d, splicex, i, mode = r
				x2 = x
				n2 = n
				if self.Constrained == 1 :
					depth2 = depth
					newtag = (x, y1, n, f, startx, m, depth, splicex, i, mode)
					data.remove(r)
					data.insert(0, newtag)
				else :
					depth2 = d

			holenoA = 'x'
			holenoB = 'x'
			corenoA = -1
			corenoB = -1
			typeA = ''
			typeB = ''
			count = 0
			for s in self.DrawData["CoreInfo"]:
				data = s
				for r in data:
					if r[0] == n2 :
						holenoA = r[3]
						corenoA = r[4]
						typeA = r[10]
						count = count + 1
					elif r[0] == n1 :
						holenoB = r[3]
						corenoB = r[4]
						typeB = r[10]
						count = count + 1
					if count >= 2:
						break
				if count >= 2:
					break
	
			shift = depth2 - depth 
			self.OnUpdateSPGuideData(self.activeCore, depth, shift)
			if self.Constrained == 0 :
				self.parent.splicePanel.OnUpdateDepth(shift)

			self.parent.splicePanel.OnButtonEnable(0, True)
			flag = self.parent.showELDPanel | self.parent.showCompositePanel | self.parent.showSplicePanel
			if flag == 1 :

				testret = py_correlator.evalcoef_splice(typeB, holenoB, int(corenoB), depth, depth2)
				if testret != "" :
					self.parent.OnAddFirstGraph(testret, depth2, depth)

				for data_item in self.range :
					if data_item[0] == "Natural Gamma" and typeA == "NaturalGamma" :
						typeA = "Natural Gamma"
					elif data_item[0] == "NaturalGamma" and typeA == "Natural Gamma" :
						typeA = "NaturalGamma"
					if data_item[0] != typeA and data_item[0] != "splice" and data_item[0] != "log" :
						testret = py_correlator.evalcoef_splice(data_item[0], holenoB, int(corenoB), depth, depth2)
						if testret != "" :
							self.parent.OnAddGraph(testret, depth2, depth)
				self.parent.OnUpdateGraph()

		else :
			if len(self.LogTieData) < self.activeSATie :
				self.activeSATie = -1
				return

			data = self.LogTieData[self.activeSATie]
			x1 = 0
			x2 = 0
			y1 = 0
			y2 = 0
			n2 = -1 
			currentY = 0
			for r in data :
				x, y, n, f, startx, m, d, splicex, i, raw = r
				n1 = n
				x1 = x
				y1 = d + shift_delta
				y = self.startDepth + (y1 - self.SPrulerStartDepth) * (self.length / self.gap)
				newtag = (x, y, n, f, startx, m, y1, splicex, i, raw)
				data.remove(r)
				data.insert(0, newtag)

			self.saganDepth = y1

			data = self.LogTieData[self.activeSATie - 1]
			for r in data :
				x2 = r[0]
				y2 = r[6]
				n2 = r[2] 

			holenoA = 'x'
			corenoA = -1
			count = 0
			for s in self.DrawData["CoreInfo"]:
				data = s
				for r in data:
					if r[0] == n2 :
						holenoA = r[3]
						corenoA = r[4]
						count = count + 1
						break
				if count >= 1:
					break

			count = 0
			if len(self.SpliceCore) == 1 :
				self.PreviewNumTies = 0
				for i in range(self.parent.eldPanel.fileList.GetCount()) :
					start = 0
					last = 0
					data = self.parent.eldPanel.fileList.GetString(i)
					last = data.find(" ", start) # hole
					temp_hole = data[start:last]
					start = last + 1
					last = data.find(" ", start) # core
					temp_core = data[start:last]
					if temp_hole == holenoA and temp_core == corenoA :
						self.PreviewFirstNo = count * 2 + 1
						self.PreviewNumTies = 1
						break
					count = count + 1

			self.PreviewLog = [-1, -1, 1.0, 0, -1, -1, 1.0]
			if len(self.LogTieData) == 2 or self.PreviewNumTies == 0 :
				self.PreviewFirstNo = self.activeSATie
				self.PreviewLog[3] = y1 - y2
				if self.Flating == False :				
					self.PreviewLog[0] = self.FirstDepth 
					self.PreviewLog[1] = y2
					self.PreviewLog[2] = (y1 - self.FirstDepth) / (y2 - self.FirstDepth)
					self.PreviewLog[3] = y1 - y2

					if (self.activeSATie + 2) < len(self.LogTieData) :
						data = self.LogTieData[self.activeSATie + 1]
						for r in data :
							y3 = r[6]
						self.PreviewLog[4] = y2
						self.PreviewLog[5] = y3
						self.PreviewLog[6] = (y3 - y1) / (y3 - y2)
			else :
				y3 = 0
				data = self.LogTieData[self.activeSATie - 2]
				for r in data :
					y3 = r[6]
				self.PreviewLog[2] = (y1 - y3) / (y2 - y3)
				self.PreviewLog[0] = y3
				self.PreviewLog[1] = y2
				if (self.activeSATie + 2) < len(self.LogTieData) :
					data = self.LogTieData[self.activeSATie + 1]
					for r in data :
						y3 = r[6]
					self.PreviewLog[4] = y2
					self.PreviewLog[5] = y3
					self.PreviewLog[6] = (y3 - y1) / (y3 - y2)

			flag = self.parent.showELDPanel | self.parent.showCompositePanel | self.parent.showSplicePanel
			if holenoA != 'x' and flag == 1 :
				testret = py_correlator.evalcoefLog(holenoA, int(corenoA), y2, y1)
				if testret != "" :
					self.parent.OnAddFirstGraph(testret, y2, y1)
					self.parent.OnUpdateGraph()


	def OnRMouse(self, event):
		if self.MainViewMode == True :
			self.OnMainRMouse(event)
		else :
			self.OnAgeDepthRMouse(event)

	def OnAgeDepthRMouse(self, event):
		pass

	def OnMainRMouse(self, event):
		pos = event.GetPositionTuple()
		self.selectedTie = -1 

		dotsize_x = self.tieDotSize + self.holeWidth + 10 
		dotsize_y = self.tieDotSize + 10 
		half = dotsize_y / 2

		count = 0
		for data in self.TieData:
			for r in data :
				y = self.startDepth + (r[6] - self.rulerStartDepth) * (self.length / self.gap)
				x = (r[0] * self.holeWidth) + (r[0] * 50) + 50 - self.minScrollRange
				reg = None
				reg = wx.Rect(x - half, y - half, dotsize_x, dotsize_y)

				if reg.Inside(wx.Point(pos[0], pos[1])):
					self.selectedTie = count
					self.showMenu = True
					popupMenu = wx.Menu()
					# create Menu
					popupMenu.Append(1, "&Clear")
					wx.EVT_MENU(popupMenu, 1, self.OnTieSelectionCb)
					if r[3] == 0 : # move tie	
						popupMenu.Append(3, "&Adjust depth with this core and all below")
						wx.EVT_MENU(popupMenu, 3, self.OnTieSelectionCb)
						popupMenu.Append(2, "&Adjust depth with this core only")
						wx.EVT_MENU(popupMenu, 2, self.OnTieSelectionCb)

						popupMenu.Append(4, "&Undo to previous offset")
						wx.EVT_MENU(popupMenu, 4, self.OnTieSelectionCb)
						popupMenu.Append(5, "&Undo to offset of core above")
						wx.EVT_MENU(popupMenu, 5, self.OnTieSelectionCb)

					self.parent.PopupMenu(popupMenu, event.GetPositionTuple())
					return
			count = count + 1

		count = 0
		for data in self.SpliceTieData:
			for r in data :
				y = self.startDepth + (r[6] - self.SPrulerStartDepth) * (self.length / self.gap)
				x = self.splicerX + 50
				reg = None
				if (count % 2) == 1 :
					x += self.holeWidth + 50
				reg = wx.Rect(x - half, y - half, dotsize_x, dotsize_y)

				if reg.Inside(wx.Point(pos[0], pos[1])):
					self.SPselectedTie = count
					popupMenu = wx.Menu()
					self.showMenu = True
					# create Menu
					popupMenu.Append(1, "&Clear")
					wx.EVT_MENU(popupMenu, 1, self.OnSpliceTieSelectionCb)
					if r[3] == 0 : # move tie	
						popupMenu.Append(2, "&Set")
						wx.EVT_MENU(popupMenu, 2, self.OnSpliceTieSelectionCb)
					self.parent.PopupMenu(popupMenu, event.GetPositionTuple())
					return
			count = count + 1

		count = 0
		for data in self.LogTieData:
			for r in data :
				x = self.splicerX + self.holeWidth + 100
				y = self.startDepth + (r[6] - self.SPrulerStartDepth) * (self.length / self.gap)
				reg = None
				if (count % 2) == 1 :
					x += self.holeWidth + 50
				reg = wx.Rect(x - half, y - half, dotsize_x, dotsize_y)

				if reg.Inside(wx.Point(pos[0], pos[1])):
					self.LogselectedTie = count
					self.showMenu = True
					popupMenu = wx.Menu()
					# create Menu
					popupMenu.Append(1, "&Clear")
					wx.EVT_MENU(popupMenu, 1, self.OnLogTieSelectionCb)
					if r[3] == 0 : # move tie	
						popupMenu.Append(2, "&Set")
						wx.EVT_MENU(popupMenu, 2, self.OnLogTieSelectionCb)
					self.parent.PopupMenu(popupMenu, event.GetPositionTuple())
					return
			count = count + 1

		if pos[0] <= self.splicerX :
			#if len(self.DrawData["MouseInfo"]) > 0 :
			for mouse in self.DrawData["MouseInfo"] :
				idx = mouse[0]
				for data in self.DrawData["CoreInfo"] :
					for info in data :
						if idx == info[0] :
							popupMenu = wx.Menu()
							#if info[11] == '0' :
							#	popupMenu.Append(1, "&Register it as Bad Core")
							#	wx.EVT_MENU(popupMenu, 1, self.OnSetQTCb)
							#else :	
							#	popupMenu.Append(2, "&Register it as Good Core")
							#	wx.EVT_MENU(popupMenu, 2, self.OnSetQTCb)

							#popupMenu.Append(4, "&Select for Splicing")
							#wx.EVT_MENU(popupMenu, 4, self.OnSetQTCb)

							if self.parent.client != None :
								popupMenu.Append(3, "&Show it on Corelyzer")
								wx.EVT_MENU(popupMenu, 3, self.OnSetQTCb)

							self.parent.PopupMenu(popupMenu, event.GetPositionTuple())
							return
				break

			
		#popupMenu = wx.Menu()
		#popupMenu.Append(1, "&Unsmoothed only")
		#wx.EVT_MENU(popupMenu, 1, self.OnSetFunction)
		#popupMenu.Append(2, "&Smoothed only")
		#wx.EVT_MENU(popupMenu, 2, self.OnSetFunction)
		#popupMenu.Append(3, "&Smoothed & Unsmoothed")
		#wx.EVT_MENU(popupMenu, 3, self.OnSetFunction)
		#popupMenu.Append(4, "&Undo decimate")
		#wx.EVT_MENU(popupMenu, 4, self.OnSetFunction)
		#popupMenu.Append(5, "&Clear all ties")
		#wx.EVT_MENU(popupMenu, 5, self.OnSetFunction)
		#self.parent.PopupMenu(popupMenu, event.GetPositionTuple())

	def OnLMouse(self, event):
		pos = event.GetPositionTuple()
		for key, data in self.DrawData.items():
			if key == "Interface":
				bmp, x, y = data
				x = self.Width + x
				w, h = bmp.GetWidth(), bmp.GetHeight()
				reg = wx.Rect(x, y, w, h)
				if reg.Inside(wx.Point(pos[0], pos[1])):				 
					if self.isSecondScroll == 1 :
						self.grabScrollB = 1	
					elif self.isSecondScroll == 0 :
						self.grabScrollA = 1	
					self.UpdateDrawing()
			elif key == "MovableInterface":
				bmp, x, y = data
				x = x + self.splicerX - 40
				w, h = bmp.GetWidth(), bmp.GetHeight()
				reg = wx.Rect(x, y, w, h)
				if reg.Inside(wx.Point(pos[0], pos[1])):				 
					self.grabScrollA = 1	
					self.UpdateDrawing()
			elif key == "MovableSkin" and self.spliceWindowOn == 1 :
				bmp, x, y = data
				x = x + self.splicerX - 40
				w, h = bmp.GetWidth(), bmp.GetHeight()
				w = self.ScrollSize
				reg = wx.Rect(x, pos[1], w, h)
				if reg.Inside(wx.Point(pos[0], pos[1])):
					self.selectScroll = 1
			elif key == "HScroll":
				bmp, x, y = data
				y = self.Height + y
				w, h = bmp.GetWidth(), bmp.GetHeight()
				reg = wx.Rect(x, y, w, h)
				if reg.Inside(wx.Point(pos[0], pos[1])):				 
					self.grabScrollC = 1	

		if self.MainViewMode == True :
			self.OnMainLMouse(event)
		else :
			self.OnAgeDepthLMouse(event)


	def OnAgeDepthLMouse(self, event):
		if self.AgeEnableDrag == True :
			pos = event.GetPositionTuple()
			for data in self.DrawData["CoreArea"] :
				for r in data :
					n, x, y, w, h, min, max, hole_idx = r
					reg = wx.Rect(x, y, w, h)
					if reg.Inside(wx.Point(pos[0], pos[1])):
						self.SelectedAge = n
						self.mouseX = pos[0]
						self.mouseY = pos[1]
						self.drag = 1
						return


	def OnMainLMouse(self, event):
		# check left or right
		pos = event.GetPositionTuple()
		self.selectedTie = -1 
		self.activeTie = -1
		self.activeSPTie = -1
		self.activeSATie = -1

		# move tie
		count = 0
		dotsize_x = self.tieDotSize + self.holeWidth + 10 
		dotsize_y = self.tieDotSize + 10 
		half = dotsize_y / 2
		for data in self.TieData:
			for r in data :
				y = self.startDepth + (r[6] - self.rulerStartDepth) * (self.length / self.gap)
				x = (r[0] * self.holeWidth) + (r[0] * 50) + 50 - self.minScrollRange
				reg = wx.Rect(x - half, y - half, dotsize_x, dotsize_y)
				if reg.Inside(wx.Point(pos[0], pos[1])):
					if r[3] == 0 : 
						self.selectedTie = count
						if (count % 2) == 1 : 
							self.activeTie = count
						return
			count = count + 1

		count = 0
		for data in self.SpliceTieData:
			for r in data :
				if (count % 2) == 1 : 
					y = self.startDepth + (r[6] - self.SPrulerStartDepth) * (self.length / self.gap)

					x = self.splicerX + self.holeWidth + 100
					reg = wx.Rect(x - half, y - half, dotsize_x, dotsize_y)
					if reg.Inside(wx.Point(pos[0], pos[1])):
						if r[3] == 0 : 
							self.SPselectedTie = count
					 		self.activeSPTie = count
							return
			count = count + 1

		count = 0
		for data in self.LogTieData:
			for r in data :
				if (count % 2) == 1 : 
					y = self.startDepth + (r[6] - self.SPrulerStartDepth) * (self.length / self.gap)
					x = self.splicerX + self.holeWidth * 2 + 150
					reg = wx.Rect(r[0] - half, y - half, dotsize_x, dotsize_y)
					if reg.Inside(wx.Point(pos[0], pos[1])):
						if r[3] == 0 : 
							self.LogselectedTie = count
							self.activeSATie = count
							return
			count = count + 1


		# grab core --> for copy core to splice space
		if self.selectScroll == 0 :
			if pos[0] <= self.splicerX :
				for key, data in self.DrawData.items():
					if key == "CoreArea":
						for s in data :
							area = s
							for r in area:
								n, x, y, w, h, min, max, hole_idx = r
								reg = wx.Rect(min, y, max, h)
								if reg.Inside(wx.Point(pos[0], pos[1])):
									self.grabCore = n

			if pos[0] > self.splicerX :
				for key, data in self.DrawData.items():
					if key == "SpliceArea":
						for s in data :
							area = s
							for r in area:
								n, x, y, w, h, min, max = r
								reg = wx.Rect(min, y, max, h)
								if reg.Inside(wx.Point(pos[0], pos[1])):
									self.SPgrabCore = n

		# make tie 
		if self.pressedkeyShift == 1 :
		 if self.drag == 0 :
			 for key, data in self.DrawData.items():
					if key == "CoreArea":
						for s in data :
							area = s 
							for r in area:
								n, x, y, w, h, min, max, hole_idx = r
								reg = wx.Rect(min, y, max, h)
								if reg.Inside(wx.Point(pos[0], pos[1])):
									self.drag = 1 
									self.selectedCore = n 
									self.mouseX = pos[0] 
									self.mouseY = pos[1] 
									self.currentStartX = min 
									self.currentHole = hole_idx 
									break;
							if self.drag == 1 :
								break
					elif key == "SpliceArea":
						for s in data :
							area = s 
							for r in area:
								n, x, y, w, h, min, max = r
								reg = wx.Rect(min, y, max, h)
								if reg.Inside(wx.Point(pos[0], pos[1])):
									self.drag = 1 
									self.selectedCore = n 
									self.mouseX = pos[0] 
									self.mouseY = pos[1] 
									self.currentStartX = min 
									self.spliceTie = 1
									break
							if self.drag == 1 :
								break
					elif key == "LogArea" :
						for s in data :
							area = s 
							for r in area:
								n, x, y, w, h, min, max = r
								reg = wx.Rect(min, y, max, h)
								if reg.Inside(wx.Point(pos[0], pos[1])):
									self.drag = 1 
									self.selectedCore = n 
									self.mouseX = pos[0] 
									self.mouseY = pos[1] 
									self.currentStartX = min 
									self.logTie = 1
									break
							if self.drag == 1 :
								break

	def OnDataChange(self, core, shift):
		holeno = 'x'
		coreno = 0
		for s in self.DrawData["CoreInfo"]:
			data = s
			for r in data:
				if r[0] == core :
					holeno = r[3]
					coreno = r[4]
					break

		for data in self.HoleData:
			for record in data:
				holeInfo = record[0]
				if holeInfo[7] == holeno :
					count = 0
					for coredata in record :
						if coredata[0] == coreno and count != 0 :
							valuelist = coredata[10]
							count = 0
							for v in valuelist :
								x, y = v
								x = x + shift
								news = (x, y)
								valuelist.remove(v)
								valuelist.insert(count, news)
								count = count + 1
							return;
						count = 1


	def OnUpdateGuideData(self, core, shiftx, shifty):
		self.GuideCore = []

		holeno = 'x'
		coreno = '0'
		type = ""
		for s in self.DrawData["CoreInfo"]:
			data = s
			for r in data:
				if r[0] == core :
				 holeno = r[3]
				 coreno = r[4]
				 type = r[10]
				 break

		temp_type = type
		if temp_type == "Natural Gamma" :	
			temp_type = "NaturalGamma"
		smooth_id = -1
		for r in self.range :
			if r[0] == temp_type :
				smooth_id = r[4]
				break

		# 9/19/2013 brg: duplication - these routines are EXACTLY THE SAME
		# except one uses SmoothData and one uses HoleData
		if smooth_id == 1 :
			for data in self.SmoothData:
				for record in data:
					holeInfo = record[0] 
					if holeInfo[7] == holeno and type == holeInfo[2]: 
						count = 0
						for coredata in record : 
							if coredata[0] == coreno and count != 0: 
								valuelist = coredata[10]
								for v in valuelist :
									x, y = v
									x = x + shifty
									l = []
									l.append((x, y))
									self.GuideCore.append(l) 
								return;
							count = 1
		else :
			for data in self.HoleData:
				for record in data:
					holeInfo = record[0] 
					if holeInfo[7] == holeno and type == holeInfo[2]: 
						count = 0
						for coredata in record : 
							if coredata[0] == coreno and count != 0: 
								valuelist = coredata[10]
								for v in valuelist :
									x, y = v
									x = x + shifty
									l = []
									l.append((x, y))
									self.GuideCore.append(l) 
								return;
							count = 1


	def OnUpdateSPGuideData(self, core, cut, shift):
		self.SPGuideCore = []
		holeno = 'x'
		coreno = 0
		type = ""
		for s in self.DrawData["CoreInfo"]:
			data = s
			for r in data:
				if r[0] == core :
				 holeno = r[3]
				 coreno = r[4]
				 type = r[10]
				 break

		data_list = []
		if self.splice_smooth_flag == 1 :
			data_list = self.SmoothData
		else :
			data_list = self.HoleData
			

		# 9/23/2013 brgtodo duplication - it's everywhere.
		if self.Constrained == 1 :
			for data in data_list:
				for record in data:
					holeInfo = record[0]
					if holeInfo[7] == holeno and holeInfo[2] == type :
						count = 0
						for coredata in record :
							if coredata[0] == coreno and count != 0 :
								valuelist = coredata[10]
								for v in valuelist :
									x, y = v
									x = x + shift
									if x >= cut :
										l = []
										l.append((x, y))
										self.SPGuideCore.append(l) 
								return;
							count = 1 
		else :
			for data in data_list:
				for record in data:
					holeInfo = record[0]
					if holeInfo[7] == holeno and holeInfo[2] == type :
						count = 0
						for coredata in record :
							if coredata[0] == coreno and count != 0: 
								valuelist = coredata[10]
								for v in valuelist :
									x, y = v
									x = x + shift
									l = []
									l.append((x, y))
									self.SPGuideCore.append(l) 
								return;
							count = 1 

	def OnDrawGuide(self):
		if self.selectedTie < 0 :
			return
		else :
			data = self.TieData[self.selectedTie - 1]
			y1 = 0
			y2 = 0
			x2 = 0
			x = 0
			n = 0
			for r in data :
				x, y, n, f, startx, m, d = r
				y = self.startDepth + (d - self.rulerStartDepth) * (self.length / self.gap)
				y2 = (y - self.startDepth) / (self.length / self.gap) + self.rulerStartDepth
			x2 = x
			self.guideCore = n
			data = self.TieData[self.selectedTie]
			for r in data :
				x, y, n, f, startx, m, d = r
				y = self.startDepth + (d - self.rulerStartDepth) * (self.length / self.gap)
				y1 = (y - self.startDepth) / (self.length / self.gap) + self.rulerStartDepth

			shift = y2 - y1
			shiftx = x2 - x
			self.compositeDepth = y1 + shift

			self.activeCore = self.selectedCore
			self.OnUpdateGuideData(self.selectedCore, shiftx, shift)

	def GetDataInfo(self, coreindex):
		hole = '-'
		coreid = -1
		type = ''
		ret = 0
		quality = '0'
		no = -1
		for s in self.DrawData["CoreInfo"]:
			data = s
			for r in data:
				if r[0] == coreindex :
					hole = r[3]
					coreid = int(r[4])
					type = r[10]
					ret = 1
					quality = r[11]
					no = r[12]
					break
			if ret == 1:
				break
		return (hole, int(coreid), type, quality, no) 


	def isInSameHole(self, coreidA, coreidB):
		holenoA = 'x'
		holenoB = 'x' 
		count = 0
		for s in self.DrawData["CoreInfo"]:
			data = s
			for r in data:
				if r[0] == coreidA :
					holenoA = r[3]
					count = count + 1 
				if r[0] == coreidB :
					holenoB = r[3]
					count = count + 1
				if count >= 2 :
					break 
			if count >= 2:
				break

		if holenoA == 'x' or holenoB == 'x' : 
			return 0
		if holenoA != holenoB : 
			return 1
		return 0

	def UpdateAgeModel(self):
		space_bar = ""
		if platform_name[0] == "Windows" :
			space_bar = " "

		# 9/23/2013 brgtodo duplication
		for data in self.StratData :
			for r in data:
				order, hole, name, label, start, stop, rawstart, rawstop, age, type = r 
				strItem = ""
				bm0 = int(100.0 * float(rawstart)) / 100.0;
				str_ba = str(bm0)
				max_ba = len(str_ba)
				start_ba = str_ba.find('.', 0)
				str_ba = str_ba[start_ba:max_ba]
				max_ba = len(str_ba)
				if max_ba < 3 :
					strItem = strItem + str(bm0) + "0 \t"
				else :
					strItem = strItem + str(bm0) + space_bar + "\t"

				bm = int(100.0 * float(start)) / 100.0;
				str_ba = str(bm)
				max_ba = len(str_ba)
				start_ba = str_ba.find('.', 0)
				str_ba = str_ba[start_ba:max_ba]
				max_ba = len(str_ba)
				if max_ba < 3 :
					strItem += str(bm) + "0 \t" + str(bm) + "0 \t"
				else :
					strItem += str(bm) + space_bar + "\t" + str(bm) + space_bar + " \t"

				ba = int(1000.0 * float(age)) / 1000.0;
				str_ba = str(ba)
				max_ba = len(str_ba)
				start_ba = str_ba.find('.', 0)
				str_ba = str_ba[start_ba:max_ba]
				max_ba = len(str_ba)
				if max_ba < 3 :
					strItem += str(ba) + "0 \t" + label 
				else :
					strItem += str(ba) + space_bar + "\t" + label 
				ret = self.parent.agePanel.OnAddAgeToListAt(strItem, int(order))
				if ret >= 0 :
					self.AgeDataList.insert(int(order), ((self.SelectedAge, start, rawstart, age, name, label, type, 0.0)))

	def OnMouseUp(self, event):
		self.SetFocusFromKbd()
		if self.MainViewMode == True : 
			self.OnMainMouseUp(event)
		else :
			self.OnAgeDepthMouseUp(event)

	def OnAgeDepthMouseUp(self, event):
		if self.SelectedAge >= 0 :
			pos = event.GetPositionTuple()
			if self.drag == 1 :
				pos = event.GetPositionTuple()
				#self.AgeShiftX = self.AgeShiftX + pos[0] - self.mouseX
				#self.AgeShiftY = self.AgeShiftY + pos[1] - self.mouseY
				strat_size = len(self.StratData) 
				data = None
				rawstart = 0.0
				start = 0.0
				age = 0.0
				label = ""
				name = ""
				type = ""
				if self.SelectedAge < strat_size :
					data = self.StratData[self.SelectedAge]
					for r in data:
						rawstart = r[6]
						start = r[4] 
						age = r[8]
						label = r[3] 
						name = r[2] 
						type = r[9] 

						# current position
						age = (pos[0] - self.compositeX - self.AgeShiftX) / self.ageLength + self.minAgeRange 
						depth = (pos[1] - self.startAgeDepth - self.AgeShiftY) * (1.0 * self.ageGap / self.ageYLength) + self.rulerStartAgeDepth

						#preY = self.startAgeDepth + (self.firstPntDepth - self.rulerStartAgeDepth) * ( self.ageYLength / self.ageGap ) + self.AgeShiftY

						mcd = depth
						rate = py_correlator.getMcdRate(depth)
						if self.mbsfDepthPlot == 1 : # if mbsf
							mcd = depth * rate 
						else :
							depth = mcd / rate 

						l = r[0], r[1], r[2], r[3], mcd, r[5], depth, r[7], age, r[9]
						data.pop(0)
						data.insert(0, l)

				else :
					data = self.UserdefStratData[self.SelectedAge - strat_size]
					for r in data:
						#name, mcd, depth, age, comment
						rawstart = r[2]
						start = r[1] 
						age = r[3]
						label = r[0]
						name = r[4] 
						type = "handpick" 
						age = (pos[0] - self.compositeX - self.AgeShiftX) / self.ageLength + self.minAgeRange 
						depth = (pos[1] - self.startAgeDepth - self.AgeShiftY) * (1.0 * self.ageGap / self.ageYLength) + self.rulerStartAgeDepth
						mcd = depth 
						rate = py_correlator.getMcdRate(depth)
						if self.mbsfDepthPlot == 1 : # if mbsf
							mcd = depth * rate 
						else :
							depth = mcd / rate 
						l = label, mcd, depth, age, name
						data.pop(0)
						data.insert(0, l)
				self.parent.AgeChange = True
				self.UpdateDrawing()
			elif self.AgeEnableDrag == False :
				strat_size = len(self.StratData) 
				data = None
				rawstart = 0.0
				start = 0.0
				age = 0.0
				label = ""
				name = ""
				type = ""
				if self.SelectedAge < strat_size :
					data = self.StratData[self.SelectedAge]
					for r in data:
						rawstart = r[6]
						start = r[4] 
						age = r[8]
						label = r[3] 
						name = r[2] 
						type = r[9] 
				else :
					data = self.UserdefStratData[self.SelectedAge - strat_size]
					for r in data:
						#name, mcd, depth, age, comment
						rawstart = r[2]
						start = r[1] 
						age = r[3]
						label = r[0]
						name = r[4] 
						type = "handpick" 

				strItem = ""
				bm0 = int(100.00 * float(rawstart)) / 100.00;
				str_ba = str(bm0)
				max_ba = len(str_ba)
				start_ba = str_ba.find('.', 0)
				str_ba = str_ba[start_ba:max_ba]
				max_ba = len(str_ba)

				# 9/23/2013 brgtodo duplication candidate
				if platform_name[0] != "Windows" :
					if max_ba < 3 :
						strItem = strItem + str(bm0) + "0 \t"
					else :
						strItem = strItem + str(bm0) + "\t"

					bm = int(100.00 * float(start)) / 100.00;
					str_ba = str(bm)
					max_ba = len(str_ba)
					start_ba = str_ba.find('.', 0)
					str_ba = str_ba[start_ba:max_ba]
					max_ba = len(str_ba)
					if max_ba < 3 :
						strItem += str(bm) + "0 \t" + str(bm) + "0 \t"
					else :
						strItem += str(bm) + "\t" + str(bm) + "\t"

					ba = int(1000.00 * float(age)) / 1000.00;
					str_ba = str(ba)
					max_ba = len(str_ba)
					start_ba = str_ba.find('.', 0)
					str_ba = str_ba[start_ba:max_ba]
					max_ba = len(str_ba)
					if max_ba < 3 :
						strItem += str(ba) + "0 \t" + label 
					else :
						strItem += str(ba) + "\t" + label 
					if type == "handpick"  :
						strItem += " *handpick"
				else :
					if max_ba < 3 :
						strItem = strItem + str(bm0) + "0 \t"
					else :
						strItem = strItem + str(bm0) + " \t"

					bm = int(100.00 * float(start)) / 100.00;
					str_ba = str(bm)
					max_ba = len(str_ba)
					start_ba = str_ba.find('.', 0)
					str_ba = str_ba[start_ba:max_ba]
					max_ba = len(str_ba)
					if max_ba < 3 :
						strItem += str(bm) + "0 \t" + str(bm) + "0 \t"
					else :
						strItem += str(bm) + " \t" + str(bm) + " \t"

					ba = int(1000.00 * float(age)) / 1000.00;
					str_ba = str(ba)
					max_ba = len(str_ba)
					start_ba = str_ba.find('.', 0)
					str_ba = str_ba[start_ba:max_ba]
					max_ba = len(str_ba)
					if max_ba < 3 :
						strItem += str(ba) + "0 \t" + label 
					else :
						strItem += str(ba) + " \t" + label 
					if type == "handpick"  :
						strItem += " *handpick"                                       

				ret = self.parent.agePanel.OnAddAgeToList(strItem)
				if ret >= 0 :
					self.AgeDataList.insert(ret, (self.SelectedAge, start, rawstart, age, name, label, type, 0.0))
					self.parent.TimeChange = True
					self.UpdateDrawing()

		self.drag = 0
		self.SelectedAge = -1
		self.grabScrollA = 0
		self.grabScrollB = 0
		self.grabScrollC = 0
		self.selectScroll = 0


	def OnMainMouseUp(self, event):
		pos = event.GetPositionTuple()

		if self.showMenu == True :
			self.selectedTie = -1
			self.activeTie = -1
			self.showMenu = False
			self.selectedCore = -1
			self.spliceTie = -1
			self.logTie = -1
			self.drag = 0
			self.mouseX = 0
			self.mouseY = 0
			return

		self.selectScroll = 0
		if self.grabScrollA == 1 :
			self.UpdateScrollA(pos)

			self.grabScrollA = 0
			self.selectScroll = 0 
			self.UpdateDrawing()
			return

		if self.grabScrollB == 1 :
			scroll_start = self.startDepth * 0.7
			scroll_y = pos[1] - scroll_start
			if scroll_y < scroll_start :
				scroll_y = scroll_start
			scroll_width = self.Height - (self.startDepth * 1.6)
			if scroll_y > scroll_width :
				scroll_y = scroll_width

 			bmp, x, y = self.DrawData["Interface"]
 			self.DrawData["Interface"] = (bmp, x, scroll_y)

 			bmp, x, y = self.DrawData["Skin"]
 			self.DrawData["Skin"] = (bmp, x, scroll_y)

			scroll_width = scroll_width - scroll_start 
			rate = (scroll_y - scroll_start) / (scroll_width * 1.0)
			self.SPrulerStartDepth = int(self.parent.ScrollMax * rate * 100.0) / 100.0

			self.grabScrollB = 0
			self.UpdateDrawing()
			return ;

		if self.grabScrollC == 1 :
			scroll_start = self.compositeX
			scroll_x = pos[0]
			if scroll_x < scroll_start :
				scroll_x = scroll_start
			scroll_width = self.splicerX - (self.startDepth * 2.3) 
			if scroll_x > scroll_width :
				scroll_x = scroll_width

			bmp, x, y = self.DrawData["HScroll"]
			self.DrawData["HScroll"] = (bmp, scroll_x, y)

			scroll_width = scroll_width - scroll_start 
			rate = (scroll_x - scroll_start) / (scroll_width * 1.0)
			self.minScrollRange = int(self.parent.HScrollMax * rate)

			self.grabScrollC = 0
			self.UpdateDrawing()
			return ;

		if pos[0] >= self.splicerX :
			if self.grabCore >= 0 :
				if self.parent.splicePanel.appendall == 1 :
					self.parent.OnShowMessage("Error", "Appending all blocks more splicing", 1)
					self.grabCore = -1
					return
				# grab by default
				splice_count = len(self.SpliceCore)
				if self.isLogMode == 1 and self.parent.splicedOpened == 0 : 
					ret = self.GetDataInfo(self.grabCore)
					type = self.GetTypeID(ret[2])
					sagan_hole = ret[4]
					self.hole_sagan = sagan_hole 
					self.sagan_type = ret[2] 
					self.autocoreNo = []
					type_temp = ret[2]

					smooth_id = -1 
					for r in self.range :
						if r[0] == ret[2] :
							smooth_id = r[4] 
							break

					self.SpliceData = []
					self.SpliceSmoothData = []
					# 0(unsmooth), 1(smooth), 2(both)
					ret = py_correlator.getHoleData(sagan_hole, 0)
					if ret != "" :
						self.parent.filterPanel.OnLock()
						self.parent.ParseData(ret, self.SpliceData)
						self.parent.filterPanel.OnRelease()
					ret = py_correlator.getHoleData(sagan_hole, 2)
					if ret != "" :
						self.parent.filterPanel.OnLock()
						self.parent.ParseData(ret, self.SpliceSmoothData)
						self.parent.filterPanel.OnRelease()

					self.SpliceCore = []
					for s in self.DrawData["CoreInfo"]:
						data = s
						for r in data:
							if r[12] == sagan_hole :
								self.SpliceCore.append(r[0])

					self.LogSpliceData = []
					self.LogSpliceSmoothData = []
					icount = 0
					for data in self.SmoothData:
						for r in data:
							if icount == sagan_hole :
								hole = r 
								l = []
								l.append(hole)
								self.LogSpliceSmoothData.append(l)
								break
						if self.LogSpliceSmoothData != [] :
							break
						icount += 1 
					icount = 0
					for data in self.HoleData:
						for r in data:
							if icount == sagan_hole :
								hole = r 
								l = []
								l.append(hole)
								self.LogSpliceData.append(l)
								break
						if self.LogSpliceData != [] :
							break
						icount += 1 

					new_r = None
					splice_range = None
					if type_temp == "Natural Gamma" :
						type_temp = "NaturalGamma"
					for r in self.range :
						if r[0] == type_temp :
							new_r = r 
						elif r[0] == "splice" :
							splice_range = r

					newrange = "splice", new_r[1], new_r[2], new_r[3], smooth_id, new_r[5] 
					if splice_range != None :
						self.range.remove(splice_range)
					self.range.append(newrange)

					self.grabCore = -1
					self.UpdateDrawing()
					return
				if self.spliceCount == 0 :
					ret = self.GetDataInfo(self.grabCore)
					if ret[3] == '0': 
						#type = self.GetTypeID(ret[2])
						type = ret[2]
						splice_data = py_correlator.first_splice(ret[0], ret[1], self.parent.smoothDisplay, 0, type)
						self.parent.splicePanel.OnButtonEnable(4, True)
						self.autocoreNo = []
						type = self.GetTypeID(ret[2])

						s = "Splice(First): hole " + str(ret[0]) + " core " + str(ret[1]) + ", " + str(type) + "\n\n"
						self.parent.logFileptr.write(s)

						self.parent.filterPanel.OnRegisterSplice()
						new_r = None
						splice_range = None
						type_temp = ret[2]
						if type_temp == "Natural Gamma" :
							type_temp = "NaturalGamma"
						for r in self.range :
							if r[0] == type_temp :
								new_r = r 
							elif r[0] == "splice" :
								splice_range = r

						newrange = "splice", new_r[1], new_r[2], new_r[3], 0, new_r[5] 
						if splice_range != None :
							self.range.remove(splice_range)
						self.range.append(newrange)

						self.multipleType = False 

						py_correlator.saveAttributeFile(self.parent.CurrentDir + 'tmp.splice.table'  , 2)
						self.parent.SpliceChange = True
						self.parent.SpliceSectionSend(ret[0], str(ret[1]), -1, "first", -1)
						self.selectedType = ret[2]
						self.PreviewFirstNo = 0
						
						self.SpliceCore.append(self.grabCore)
						self.PreviousSpliceCore = self.grabCore 
						self.spliceCount = self.spliceCount + 1

						self.Lock = True
						self.parent.UpdateSPLICE(False)
						self.parent.UpdateSMOOTH_SPLICE(False)
						if self.ShowLog == True :
							self.parent.UpdateLOGSPLICE(False)
							self.parent.UpdateSMOOTH_LOGSPLICE(False)
						self.Lock = False
					else :
						self.parent.OnShowMessage("Error", "Splice must begin with topmost core of any hole", 1)

				elif self.spliceCount == splice_count and self.isLogMode == 0 : 
					ret = self.GetDataInfo(self.grabCore)
					if ret[3] == '0': 
						# INFORMATION - for Multiple data type splice
						#if self.selectedType == ret[2] :
						if True :
							index = len(self.SpliceCore) - 1
							self.PreviousSpliceCore = self.SpliceCore[index]
							self.SpliceCore.append(self.grabCore)
							if self.PreviousSpliceCore >= 0 : 
								result = self.isInSameHole(self.grabCore, self.PreviousSpliceCore)
								if result == 1 :
									self.CurrentSpliceCore = self.grabCore
									self.PreviousSpliceCore = self.CurrentSpliceCore
								else : 
									self.parent.OnShowMessage("Error", "It should be from different hole.", 1)
									self.SpliceCore.pop()
						else :
							self.parent.OnShowMessage("Error", "Please select same type", 1)

						# UPDATE SETTYPE FOR SPLICE
						type = ret[2]
						if type == "Natural Gamma" :
							type = "NaturalGamma"
						rangePrev = 0.0
						rangeNew = 0.0
						min = 0.0
						max = 0.0
						if self.selectedType != type :
							for r in self.range :
								if r[0] == type :
									rangeNew = r[3]
									min = r[1]
									max = r[2]
								elif r[0] == self.selectedType :
									rangePrev = r[3]

						if rangeNew > rangePrev :
							self.selectedType = type 
							self.UpdateRANGE("splice", min, max)
						if type != self.selectedType :
							#print "[DEBUG] splice type is changed : " + str(self.selectedType)
							self.multipleType = True
					else :
						self.parent.OnShowMessage("Error", "Splice must begin with topmost core of any hole", 1)
				self.grabCore = -1
				self.UpdateDrawing()
				return
		else :
			self.grabCore = -1

		if pos[0] < self.splicerX :
			splice_count = len(self.SpliceCore)
			if self.SPgrabCore >= 0 :
				if self.isLogMode == 1 : 
					self.LogSpliceData = []
					self.LogSpliceSmoothData = []
					self.SpliceData = []
					self.SpliceSmoothData = []
					self.hole_sagan = -1
				elif splice_count == 1 :
					self.PreviousSpliceCore = -1
					self.CurrentSpliceCore = -1
					splice_data = py_correlator.delete_splice(-1, self.parent.smoothDisplay)
					self.parent.splicePanel.OnButtonEnable(4, False)

					s = "Splice undo last spliced tie: " + str(datetime.today()) + "\n\n"
					self.parent.logFileptr.write(s)

					self.parent.SpliceChange = True
					py_correlator.saveAttributeFile(self.parent.CurrentDir + 'tmp.splice.table'  , 2)
					self.parent.UndoSpliceSectionSend()
					self.selectedType = "" 

					if self.isLogMode == 1 : 
						self.LogSpliceData = []
						#self.LogTieData=[]
						py_correlator.fixed_sagan()

					self.SpliceData = []
					self.SpliceSmoothData = []
					self.SpliceCore = []
					self.spliceCount = 0
				else : 
					if splice_count > self.spliceCount : 
						size = splice_count
						if size > 0 :
							self.SpliceCore.pop();
							size = size - 1
							if size > 1 :
								self.CurrentSpliceCore = self.SpliceCore[size - 1]
								self.PreviousSpliceCore = -1
							else : 
								self.CurrentSpliceCore = -1
								self.PreviousSpliceCore = -1
							size = size - 1
							if size > 0 :
								self.PreviousSpliceCore = self.SpliceCore[size - 1]
				self.SPgrabCore = -1
				self.UpdateDrawing()
				return
		else :
			self.SPgrabCore = -1

		if self.selectScroll == 1 :
			self.selectScroll = 0 
			return

		currentY = pos[1]
		if self.selectedTie >= 0 : 
			data = self.TieData[self.selectedTie]

			n = 0
			for r in data :
				x, y, n, f, startx, m, d = r
				d = (pos[1] - self.startDepth) / (self.length / self.gap) + self.rulerStartDepth

			if self.selectedCore != n :
				return

			for r in data :
				x, y, n, f, startx, m, d = r
				d = (pos[1] - self.startDepth) / (self.length / self.gap) + self.rulerStartDepth
				newtag = (x, pos[1], n, f, startx, m, d)
				data.remove(r)
				data.insert(0, newtag)
				
			self.selectedCore = n
			self.selectedLastTie = self.selectedTie 
			self.GuideCore = []	
			# draw guide 
			self.OnDrawGuide()
			self.selectedTie = -1 

		if self.SPselectedTie >= 0 : 
			data = self.SpliceTieData[self.SPselectedTie]
			self.SPselectedLastTie = self.SPselectedTie 
			for r in data :
				x, y, n, f, startx, m, d, splicex, i, mode = r
				depth = (pos[1] - self.startDepth) / (self.length / self.gap) + self.SPrulerStartDepth
				newtag = (x, pos[1], n, f, startx, m, depth, self.splicerX, i, mode)
				data.remove(r)
				data.insert(0, newtag)
				tempCore = n
		
				if self.Constrained == 1 :
					predata = self.SpliceTieData[self.SPselectedTie - 1]
					for prer in predata :
						x, y, n, f, startx, m, d, splicex, i, mode = prer
						predata.remove(prer)
						newtag = x, pos[1], n, f, startx, m, depth , self.splicerX, i, mode
						predata.insert(0, newtag)
				self.parent.splicePanel.OnButtonEnable(3, True)
				#self.parent.splicePanel.OnButtonEnable(1, False)

				if self.SPselectedTie < 2 :
					removeflag = False
					tiedata = self.SpliceTieData[0]
					for tier in tiedata : 
						if tier[2] == tempCore :
							removeflag = True 
					if removeflag == False : 
						tiedata = self.SpliceTieData[1]
						for tier in tiedata : 
							if tier[2] == tempCore :
								removeflag = True 

					if removeflag == True : 
						spliceTies = len(self.SpliceTieData)
						if spliceTies > 2 :
							data = self.SpliceTieData[2]
							self.SpliceTieData.remove(data)
						if spliceTies == 4 :
							data = self.SpliceTieData[2]
							self.SpliceTieData.remove(data)

			self.SPselectedTie = -1 

		if self.LogselectedTie >= 0 :
			data = self.LogTieData[self.LogselectedTie]
			for r in data :
				x, y, n, f, startx, m, d, splicex, i, raw = r
				depth = (pos[1] - self.startDepth) / (self.length / self.gap) + self.SPrulerStartDepth
				newtag = (x, pos[1], n, f, startx, m, depth, self.splicerX, i, raw)
				data.remove(r)
				data.insert(0, newtag)
				self.lastLogTie = self.LogselectedTie
			self.LDselectedTie = self.LogselectedTie 
			self.LogselectedTie = -1

		if self.drag == 1 :
			if pos[0] == self.mouseX and pos[1] == self.mouseY : 
				if self.logTie != -1 :
					logcount = self.parent.eldPanel.fileList.GetCount()
					logcount = len(self.LogTieData) - (logcount * 2)
					if self.parent.CheckAutoELD() == False :
						self.parent.OnShowMessage("Error", "Auto Correlation does not applied.", 1)
						self.selectedCore = -1
						self.spliceTie = -1
						self.logTie = -1
						self.drag = 0
						self.mouseX = 0
						self.mouseY = 0
						self.grabScrollA = 0
						self.grabScrollB = 0
						self.grabScrollC = 0
						self.UpdateDrawing()
						return

					if logcount < 2 : 
						fixed = 0 
						length = len(self.LogTieData) % 2
						if length == 0 : 
							fixed = 1 
						# Tie 
						l = []
						depth = (pos[1] - self.startDepth) / (self.length / self.gap) + self.SPrulerStartDepth
						l.append((self.currentStartX, pos[1], self.selectedCore, fixed, self.minScrollRange, self.minData, depth, self.splicerX, -1, depth))

						self.LogTieData.append(l) 

						length = len(self.LogTieData) % 2
						if length == 0 : 
							length = len(self.LogTieData) 
							self.activeSATie = length - 1
							data = self.LogTieData[length - 2]
							y1 = 0
							y2 = 0
							x1 = 0
							x2 = 0
							coreid = 0 
							currentY = 0
							for r in data :
								currentY = r[1] 
								y2 = (r[1] - self.startDepth) / (self.length / self.gap) + self.SPrulerStartDepth
								x2 = r[0] 
								coreid = r[2]
								
							data = self.LogTieData[length - 1]
							n = 0
							for r in data :
								self.mouseY = r[1] 
								y1 = (r[1] - self.startDepth) / (self.length / self.gap) + self.SPrulerStartDepth
								x1 = r[0] 
								n = r[2]

							if x1 < x2 : 
								temp = y1
								y1 = y2
								y2 = temp
								coreid = n

							# NEED TO SORT using Y2
							prePosY = 0
							countIdx = 0
							addedFlag = False 
							maxsize = length - 2
							for data in self.LogTieData:
								for r in data :
									if prePosY <= y2 and  y2 < r[6] :
										addedFlag = True
										# UPDATE ORDER 
										data1 = self.LogTieData[length - 2]
										data2 = self.LogTieData[length - 1]
										self.LogTieData.insert(countIdx, data1)
										countIdx = countIdx + 1
										self.LogTieData.insert(countIdx, data2)
										self.LDselectedTie = countIdx
										self.LogTieData.pop()
										self.LogTieData.pop()
										break
									prePosY = r[6]
								countIdx = countIdx + 1
								if addedFlag == True :
									length = countIdx
									break
								if countIdx >= maxsize :
									break

							if addedFlag == False :
								self.LDselectedTie = len(self.LogTieData) - 1 

							holenoA = 'x'
							corenoA = -1
							count = 0
							for s in self.DrawData["CoreInfo"]:
								data = s
								for r in data:
									if r[0] == coreid :
										holenoA = r[3]
										corenoA = r[4]
										count = count + 1
									if count >= 1 :
										break
								if count >= 1:
									break

							count = 0
							if len(self.SpliceCore) == 1 :
								self.PreviewNumTies = 0
								for i in range(self.parent.eldPanel.fileList.GetCount()) :
									start = 0
									last = 0
									data = self.parent.eldPanel.fileList.GetString(i)
									last = data.find(" ", start) # hole
									temp_hole = data[start:last]
									start = last + 1
									last = data.find(" ", start) # core
									temp_core = data[start:last]
									if temp_hole == holenoA and temp_core == corenoA :
										self.PreviewFirstNo = count * 2 + 1
										self.PreviewNumTies = 1
										break
									count = count + 1

							self.PreviewLog = [-1, -1, 1.0, 0, -1, -1, 1.0]
							# HYEJUNG
							if self.LDselectedTie == 1 :
								self.PreviewLog[3] = y1 - y2
								y3 = 0
								self.PreviewLog[2] = (y1 - y3) / (y2 - y3)
								self.PreviewLog[0] = y3
								self.PreviewLog[1] = y2
								if (self.LDselectedTie + 2) < len(self.LogTieData) :
									data = self.LogTieData[self.LDselectedTie + 1]
									for r in data :
										y3 = r[6]
								self.PreviewLog[4] = y2
								self.PreviewLog[5] = y3
								self.PreviewLog[6] = (y3 - y1) / (y3 - y2)
							else :
								y3 = 0
								data = self.LogTieData[length - 3]
								for r in data :
									y3 = r[6]
								self.PreviewLog[2] = (y1 - y3) / (y2 - y3)
								self.PreviewLog[0] = y3
								self.PreviewLog[1] = y2
								if (length + 1) < len(self.LogTieData) :
									data = self.LogTieData[length]
									for r in data :
										y3 = r[6]
									self.PreviewLog[4] = y2
									self.PreviewLog[5] = y3
									self.PreviewLog[6] = (y3 - y1) / (y3 - y2)

								
							flag = self.parent.showELDPanel | self.parent.showCompositePanel | self.parent.showSplicePanel
							if holenoA != 'x' and flag == 1 :
								testret = py_correlator.evalcoefLog(holenoA, int(corenoA), y2, y1)
								if testret != "" :
									self.parent.OnAddFirstGraph(testret, y2, y1)
									self.parent.OnUpdateGraph()

						self.drag = 0
						self.logTie = -1

				elif self.spliceTie == -1 : 
					if  self.LogData != [] : 
						self.parent.OnShowMessage("Error", "You can not do composite.", 1)

					else :
						fixed = 0 
						length = len(self.TieData) % 2
						if length == 0 : 
							fixed = 1 
						if len(self.TieData) < 2 : 
							# Tie 
							l = []
							d = (pos[1] - self.startDepth) / (self.length / self.gap) + self.rulerStartDepth
							#l.append( (pos[0],pos[1], self.selectedCore, fixed, self.currentStartX, self.minScrollRange, d) )
							l.append((self.currentHole, pos[1], self.selectedCore, fixed, self.currentStartX, self.minScrollRange, d))
							self.TieData.append(l) 

							self.parent.compositePanel.OnButtonEnable(2, True)
							length = len(self.TieData) % 2
							if length == 0 : 
								self.activeTie = 1
								length = len(self.TieData) 
								data = self.TieData[length - 2]
								y1 = 0
								y2 = 0
								x1 = 0
								x2 = 0
								n = 0
								for r in data :
									x, y, n, f, startx, m, d = r
									currentY = y 
									y2 = (y - self.startDepth) / (self.length / self.gap) + self.rulerStartDepth
									x2 = x
								
								self.guideCore = n 
								data = self.TieData[length - 1]
								for r in data :
									x, y, n, f, startx, m, d = r
									self.mouseY = y 
									y1 = (y - self.startDepth) / (self.length / self.gap) + self.rulerStartDepth
									x1 = x
								shift = y2 - y1 
								shiftx = (x2 - x) * (self.holeWidth + 50)
								self.compositeDepth = y1 + shift

								holenoA = 'x'
								holenoB = 'x'
								corenoA = -1
								corenoB = -1
								typeA = ''
								typeB = ''
								leg = " "
								site = " "
								count = 0
								for s in self.DrawData["CoreInfo"]:
									data = s
									for r in data:
										if r[0] == self.guideCore :
											holenoA = r[3]
											corenoA = r[4]
											typeA = r[10]
											leg = r[2]
											site = r[1]
											count = count + 1
										if r[0] == n :
											holenoB = r[3]
											corenoB = r[4]
											typeB = r[10]
											count = count + 1
										if count >= 2 :
											break
									if count >= 2:
										break

								#if typeA != typeB :
								if False :
									self.TieData.remove(l) 
									self.parent.OnShowMessage("Error", "Please select same type", 1)
								elif holenoA != 'x' and holenoA == holenoB : 
									self.TieData.remove(l) 
								else :
									self.activeCore = self.selectedCore
									self.OnUpdateGuideData(self.selectedCore, shiftx, shift)
									self.parent.OnUpdateDepth(shift)
									self.parent.TieUpdateSend(leg, site, holenoA, int(corenoA), holenoB, int(corenoB), y1, shift)
									self.parent.compositePanel.OnButtonEnable(0, True)
									flag = self.parent.showELDPanel | self.parent.showCompositePanel | self.parent.showSplicePanel
									if flag == 1 :
										testret = py_correlator.evalcoef(typeA, holenoA, int(corenoA), y2, typeB, holenoB, int(corenoB), y1)
										if testret != "" :
											self.parent.OnAddFirstGraph(testret, y2, y1)
										for data_item in self.range :
											if data_item[0] == "Natural Gamma" and typeA == "NaturalGamma" :
												typeA = "Natural Gamma"
											elif data_item[0] == "NaturalGamma" and typeA == "Natural Gamma" :
												typeA = "NaturalGamma"
											if data_item[0] != typeA and data_item[0] != "splice" and data_item[0] != "log" :
												testret = py_correlator.evalcoef(data_item[0], holenoA, int(corenoA), y2, data_item[0], holenoB, int(corenoB), y1)
												if testret != "" :
													self.parent.OnAddGraph(testret, y2, y1)

										self.parent.OnUpdateGraph()

				elif len(self.LogTieData) == 0: 
					if (len(self.RealSpliceTie) == 0 and len(self.SpliceTieData) < 2) or (len(self.RealSpliceTie) >= 2 and len(self.SpliceTieData) < 4) :
						fixed = 0 
						length = len(self.SpliceTieData) % 2
						if length == 0 : 
							fixed = 1 

						# Tie 
						l = []
						depth = (pos[1] - self.startDepth) / (self.length / self.gap) + self.SPrulerStartDepth
						if self.SPSelectedCore >= 0 : 
							l.append((self.currentStartX, pos[1], self.SPSelectedCore, fixed, self.minScrollRange, self.minData, depth, self.splicerX, -1, self.Constrained))
							self.SPSelectedCore = -1
							self.selectedCore = -1
						else :
							l.append((self.currentStartX, pos[1], self.selectedCore, fixed, self.minScrollRange, self.minData, depth, self.splicerX, -1, self.Constrained))

						self.parent.splicePanel.OnButtonEnable(1, False)
						self.parent.splicePanel.OnButtonEnable(2, True)
						self.SpliceTieData.append(l) 

						self.SPGuideCore = []	
						length = len(self.SpliceTieData) % 2

						if length == 1 and self.Constrained == 1:
							splicecoreno = len(self.SpliceCore) 
							diff = splicecoreno - (len(self.RealSpliceTie) / 2)
							if self.begin_append == True :
								diff = diff - 1

							if diff == self.SpliceDiff :
								splicecoreno = splicecoreno - 1
								self.selectedCore = self.SpliceCore[splicecoreno]
								l = []
								splicewidth = self.holeWidth + 50
								l.append((self.currentStartX, pos[1], self.selectedCore, 0, self.minScrollRange, self.minData, depth, self.splicerX, -1, self.Constrained))
								self.SpliceTieData.append(l) 
								length = 0

						if length == 0 :
							self.activeSPTie = len(self.SpliceTieData) - 1
							shift = 0.0
							y1 = 0
							y2 = 0
							n = 0
							x1 = 0
							x2 = 0
							length = len(self.SpliceTieData) 
							data = self.SpliceTieData[length - 2]
							if self.Constrained == 1 : 
								for r in data :
									x, y, n, f, startx, m, d, splicex, i, mode = r
									data.remove(r)
									newtag = x, pos[1], n, f, startx, m, depth, self.splicerX, i, mode
									data.insert(0, newtag)
									x2 = startx
							elif self.Constrained == 0 : 
								for r in data :
									x, y, n, f, startx, m, d, splicex, i, mode = r
									y2 = (y - self.startDepth) / (self.length / self.gap) + self.SPrulerStartDepth
									x2 = startx

							self.guideSPCore = n 
							data = self.SpliceTieData[length - 1]
							for r in data :
								x, y, n, f, startx, m, d, splicex, i, mode = r
								y1 = (y - self.startDepth) / (self.length / self.gap) + self.SPrulerStartDepth
								x1 = startx

							if self.Constrained == 1 : 
								y2 = y1
							elif self.Constrained == 0 : 
								shift = y2 - y1 

							self.spliceDepth = y1

							reversed = False 
							tempCore = -1
							if x2 > x1 :						
								reversed = True 
								tempCore = self.guideSPCore 
								self.guideSPCore = n 
								n = tempCore

							holenoA = 'x'
							holenoB = 'x'
							corenoA = -1
							corenoB = -1
							count = 0
							typeA = ''
							typeB = ''

							for s in self.DrawData["CoreInfo"]:
								data = s
								for r in data:
									if r[0] == self.guideSPCore :
										holenoA = r[3]
										corenoA = r[4]
										typeA = r[10]
										count = count + 1
									if r[0] == n :
										holenoB = r[3]
										corenoB = r[4]
										typeB = r[10]
										count = count + 1
									if count >= 2 :
										break
								if count >= 2:
									break
							#if typeA != typeB :
							if False :
								self.SpliceTieData.remove(l)
								self.parent.OnShowMessage("Error", "Please select same type", 1)
							elif holenoA != 'x' and holenoA == holenoB :
								self.SpliceTieData.remove(l)
							else :
								if reversed == False :
									self.activeCore = self.selectedCore
									self.OnUpdateSPGuideData(self.selectedCore, depth, shift)
								else :
									self.activeCore = tempCore
									self.OnUpdateSPGuideData(tempCore, depth, shift)

								self.parent.splicePanel.OnButtonEnable(0, True)	

								flag = self.parent.showELDPanel | self.parent.showCompositePanel | self.parent.showSplicePanel
								if flag == 1 :
									testret = py_correlator.evalcoef_splice(typeB, holenoB, int(corenoB), y1, y2)
									if testret != "" :
										if self.Constrained == 0 :
											self.parent.splicePanel.OnUpdateDepth(shift)
										self.parent.OnAddFirstGraph(testret, y2, y1)

									for data_item in self.range :
										if data_item[0] == "Natural Gamma" and typeA == "NaturalGamma" :
											typeA = "Natural Gamma"
										elif data_item[0] == "NaturalGamma" and typeA == "Natural Gamma" :
											typeA = "NaturalGamma"
										if data_item[0] != typeA and data_item[0] != "splice" and data_item[0] != "log" :
											testret = py_correlator.evalcoef_splice(data_item[0], holenoB, int(corenoB), y1, y2)
											if testret != "" :
												self.parent.OnAddGraph(testret, y2, y1)
									self.parent.OnUpdateGraph()

		self.selectedCore = -1
		self.spliceTie = -1
		self.logTie = -1
		self.drag = 0
		self.mouseX = 0
		self.mouseY = 0
		self.grabScrollA = 0
		self.grabScrollB = 0
		self.grabScrollC = 0
		self.UpdateDrawing()


	# scrollA is the CoreArea (leftmost) region
	def UpdateScrollA(self, mousePos):
		scroll_start = self.startDepth * 0.7
		scroll_y = mousePos[1] - scroll_start
		scroll_width = self.Height - (self.startDepth * 1.6)
		if scroll_y < scroll_start :		 
			scroll_y = scroll_start
		if scroll_y > scroll_width :
			scroll_y = scroll_width

		for key, data in self.DrawData.items():
			if key == "MovableInterface":
				bmp, x, y = data
				self.DrawData["MovableInterface"] = (bmp, x, scroll_y)

		if self.spliceWindowOn == 1:
			bmp, x, y = self.DrawData["MovableSkin"]
			self.DrawData["MovableSkin"] = (bmp, x, scroll_y)

		scroll_width = scroll_width - scroll_start
		rate = (scroll_y - scroll_start) / (scroll_width * 1.0)
		if self.MainViewMode == True :
			self.rulerStartDepth = int( self.parent.ScrollMax * rate * 100.0 ) / 100.0
			if self.parent.client != None :
				_depth = (self.rulerStartDepth + self.rulerEndDepth) / 2.0
				self.parent.client.send("jump_to_depth\t" + str(_depth) + "\n")
		else :
			tempDepth = int(self.parent.ScrollMax * rate) / 10
			self.rulerStartAgeDepth = tempDepth * 10
			self.SPrulerStartAgeDepth = tempDepth * 10

		if self.isSecondScroll == 0 : 
			bmp, x, y = self.DrawData["Interface"]
			self.DrawData["Interface"] = (bmp, x, scroll_y)

			bmp, x, y = self.DrawData["Skin"]
			self.DrawData["Skin"] = (bmp, x, scroll_y)

			if self.MainViewMode == True :
				self.SPrulerStartDepth = int(self.parent.ScrollMax * rate * 100.0) / 100.0

	def OnUpdateTie(self, type):
		graphNo = 0
		tieData = None
		if type == 1 : # composite
			rulerStart = self.rulerStartDepth
			tieData = self.TieData
		else : 
			rulerStart = self.SPrulerStartDepth
			tieData = self.SpliceTieData
			graphNo = 1 

		max = len(tieData)
		length = max % 2
		if length == 0 and max != 0 : 
			length = len(tieData) 
			data = tieData[length - 2]
			y1 = 0			 
			y2 = 0			 
			n1 = 0
			n2 = 0
			for r in data :				
				y2 = (r[1] - self.startDepth) / (self.length / self.gap) + rulerStart 
				n1 = r[2]				
			data = tieData[length - 1]		 
			for r in data :			 
				y1 = (r[1] - self.startDepth) / (self.length / self.gap) + rulerStart 
				n2 = r[2]				

			holenoA = 'x'
			holenoB = 'x'
			corenoA = -1
			corenoB = -1
			count = 0
			typeA = '' 
			typeB = '' 
			leg = " "
			site = " "
			for s in self.DrawData["CoreInfo"]:
				data = s
				for r in data:
					if r[0] == n1 :
						holenoA = r[3]
						corenoA = r[4]
						typeA = r[10]
						leg = r[2]
						site = r[1]
						count = count + 1
					if r[0] == n2 :
						holenoB = r[3]
						corenoB = r[4]
						typeB = r[10]
						count = count + 1
					if count >= 2 :
						break
				if count >= 2:
					break

			if type == 1 : # composite
				shift = y2 - y1
				self.parent.TieUpdateSend(leg, site, holenoA, int(corenoA), holenoB, int(corenoB), y1, shift)

			flag = self.parent.showELDPanel | self.parent.showCompositePanel | self.parent.showSplicePanel
			if holenoA != 'x' and holenoB != 'x' and flag == 1:
				if type == 1 : # composite
					testret = py_correlator.evalcoef(typeA, holenoA, int(corenoA), y2, typeB, holenoB, int(corenoB), y1)
				else :
					testret = py_correlator.evalcoef_splice(typeB, holenoB, int(corenoB), y1, y2)
				if testret != "" :
					self.parent.OnAddFirstGraph(testret, y2, y1)
				for data_item in self.range :
					if data_item[0] == "Natural Gamma" and typeA == "NaturalGamma" :
						typeA = "Natural Gamma"
					elif data_item[0] == "NaturalGamma" and typeA == "Natural Gamma" :
						typeA = "NaturalGamma"
					if data_item[0] != typeA and data_item[0] != "splice" and data_item[0] != "log" :
						if type == 1 : # composite
							testret = py_correlator.evalcoef(data_item[0], holenoA, int(corenoA), y2, data_item[0], holenoB, int(corenoB), y1)
						else :
							testret = py_correlator.evalcoef_splice(data_item[0], holenoB, int(corenoB), y1, y2)
						if testret != "" :
							self.parent.OnAddGraph(testret, y2, y1)
				self.parent.OnUpdateGraph()


	# 9/20/2012 brgtodo: duplication
	def OnMotion(self, event):
		pos = event.GetPositionTuple()

		if self.grabScrollA == 1 :
			self.UpdateScrollA(pos)
			self.UpdateDrawing()
			return ;

		if self.grabScrollB == 1 :
			scroll_start = self.startDepth * 0.7
			scroll_y = pos[1] - scroll_start
			if scroll_y < scroll_start :
				scroll_y = scroll_start
			scroll_width = self.Height - (self.startDepth * 1.6)
			if scroll_y > scroll_width :
				scroll_y = scroll_width

			bmp, x, y = self.DrawData["Interface"]
			self.DrawData["Interface"] = (bmp, x, scroll_y)

			bmp, x, y = self.DrawData["Skin"]
			self.DrawData["Skin"] = (bmp, x, scroll_y)

			scroll_width = scroll_width - scroll_start
			rate = (scroll_y - scroll_start) / (scroll_width * 1.0)
			if self.MainViewMode == True :
				self.SPrulerStartDepth = int(self.parent.ScrollMax * rate * 100.0) / 100.0
			self.UpdateDrawing()
			return ;

		if self.grabScrollC == 1 :
			scroll_start = self.compositeX
			scroll_x = pos[0] 
			if scroll_x < scroll_start :
				scroll_x = scroll_start
			scroll_width = self.splicerX - (self.startDepth * 2.3) 
			if scroll_x > scroll_width :
				scroll_x = scroll_width

			bmp, x, y = self.DrawData["HScroll"]
			self.DrawData["HScroll"] = (bmp, scroll_x, y)

			scroll_width = scroll_width - scroll_start
			rate = (scroll_x - scroll_start) / (scroll_width * 1.0)
			if self.MainViewMode == True :
				self.minScrollRange = int(self.parent.HScrollMax * rate)
			else :
				#self.minAgeRange = 3 * rate
				self.minAgeRange = self.maxAgeRange * rate

			self.UpdateDrawing()
			return ;

		if self.MainViewMode == True :
			self.OnMainMotion(event)
		else :
			self.OnAgeDepthMotion(event)

	def OnAgeDepthMotion(self, event):
		pos = event.GetPositionTuple()
		got = 0

		if self.AgeEnableDrag == True and self.SelectedAge >= 0 :
			got = 0
		else : 
			for data in self.DrawData["CoreArea"] :
				for r in data :
					n, x, y, w, h, min, max, hole_idx = r
					reg = wx.Rect(x, y, w, h)
					if reg.Inside(wx.Point(pos[0], pos[1])):
						self.SelectedAge = n
						self.UpdateDrawing()
						return
			self.SelectedAge = -1
			self.UpdateDrawing()

		if self.selectScroll == 1 and self.grabScrollA == 0 and self.grabScrollC == 0 :
			if pos[0] >= 180 and pos[0] <= (self.Width - 100):
				scroll_widthA = self.splicerX - (self.startDepth * 2.3) - self.compositeX
				scroll_widthB = self.Width - (self.startDepth * 1.6) - self.splicerX
				temp_splicex = self.splicerX
				self.splicerX = pos[0]

				bmp, x, y = self.DrawData["HScroll"]
				scroll_rate = (x - self.compositeX) / (scroll_widthA * 1.0)
				scroll_widthA = self.splicerX - (self.startDepth * 2.3) - self.compositeX
				scroll_x = scroll_widthA * scroll_rate
				scroll_x += self.compositeX
				self.DrawData["HScroll"] = (bmp, scroll_x, y)

	def OnMainMotion(self, event):
		if self.showMenu == True :
			return

		pos = event.GetPositionTuple()
		self.MousePos = pos 
		got = 0

		# brg 1/29/2014: if mouse is over options panel, don't bother proceeding - the draw
		# commands change nothing and cause GUI elements to respond sluggishly
		if self.MousePos[0] > self.Width:
			return

		#if self.drag == 0 : 
		for key, data in self.DrawData.items():
			if key == "CoreArea":
				for s in data :
					area = s 
					for r in area:
						n, x, y, w, h, min, max, hole_idx = r
						reg = wx.Rect(min, y, max, h)
						if reg.Inside(wx.Point(pos[0], pos[1])):
							got = 1
							l = []
							self.selectedCore = n

							l.append((n, pos[0], pos[1], x, 1))
							self.DrawData["MouseInfo"] = l
			elif key == "SpliceArea":
				for s in data :
					area = s 
					for r in area:
						n, x, y, w, h, min, max = r
						reg = wx.Rect(min, y, max, h)
						if reg.Inside(wx.Point(pos[0], pos[1])):
							got = 1
							l = []
							self.selectedCore = n
							l.append((n, pos[0], pos[1], x, 2))
							self.DrawData["MouseInfo"] = l

		if self.drag == 1 :
			got = 1 

		if self.selectedTie >= 0 :
			data = self.TieData[self.selectedTie]
			n = 0
			d = 0
			for r in data :
				x, y, n, f, startx, m, d = r
				d = (pos[1] - self.startDepth) / (self.length / self.gap) + self.rulerStartDepth

			if self.selectedCore != n :
				return	

			y1 = d 
			y2 = 0
			coreId = n
			data = self.TieData[self.selectedTie - 1]
			for r in data :
				x, y, n, fixed, startx, m, d = r
				y2 = (y - self.startDepth) / (self.length / self.gap) + self.rulerStartDepth
		
			shift = y2 - y1

			holeA = '-'
			holeB = '-'
			coreA = -1
			coreB = -1
			count = 0
			typeA = ''
			typeB = ''
			leg = " "
			site = " "
			for s in self.DrawData["CoreInfo"]:
				data = s
				for r in data:
					if r[0] == coreId :
						holeA = r[3]
						coreA = r[4]
						typeA = r[10]
						leg = r[2]
						site = r[1]
						count = count + 1
					if r[0] == n :
						holeB = r[3]
						coreB = r[4]
						typeB = r[10]
						count = count + 1
					if count >= 2:
						break
				if count >= 2 :
					break

			if self.parent.showCompositePanel == 0 :
				data = self.TieData[self.selectedTie]
				for r in data :
					x, y, n, f, startx, m, d = r
					d = y1
					newtag = (x, pos[1], n, f, startx, m, d)
					data.remove(r)
					data.insert(0, newtag)
			
			self.parent.TieUpdateSend(leg, site, holeB, int(coreB), holeA, int(coreA), y1, shift)

			flag = self.parent.showELDPanel | self.parent.showCompositePanel | self.parent.showSplicePanel
			if holeA != '-' and holeB != '-' and flag == 1:
				testret = py_correlator.evalcoef(typeB, holeB, int(coreB), y2, typeA, holeA, int(coreA), y1)
				if testret != "" :
					data = self.TieData[self.selectedTie]
					for r in data :
						x, y, n, f, startx, m, d = r
						d = y1
						newtag = (x, pos[1], n, f, startx, m, d)
						data.remove(r)
						data.insert(0, newtag)
					self.parent.OnUpdateDepth(shift)
					self.parent.OnAddFirstGraph(testret, y2, y1)

				for data_item in self.range :
					if data_item[0] == "Natural Gamma" and typeA == "NaturalGamma" :
						typeA = "Natural Gamma"
					elif data_item[0] == "NaturalGamma" and typeA == "Natural Gamma" :
						typeA = "NaturalGamma"
					if data_item[0] != typeA and data_item[0] != "splice" and data_item[0] != "log" :
						testret = py_correlator.evalcoef(data_item[0], holeB, int(coreB), y2, data_item[0], holeA, int(coreA), y1)
						if testret != "" :
							self.parent.OnAddGraph(testret, y2, y1)
				self.parent.OnUpdateGraph()

			self.selectedCore = coreId 
			self.GuideCore = []
			# draw guide
			self.OnDrawGuide()
			got = 1

		if self.SPselectedTie >= 0 :
			data = self.SpliceTieData[self.SPselectedTie]
			depth = 0
			shift = 0
			y1 = 0
			y2 = 0
			x1 = 0
			x2 = 0
			for r in data :
				x, y, n, f, startx, m, d, splicex, i, mode = r
				depth = (pos[1] - self.startDepth) / (self.length / self.gap) + self.SPrulerStartDepth
				newtag = (x, pos[1], n, f, startx, m, depth, self.splicerX, i, mode)
				data.remove(r)
				data.insert(0, newtag)
				self.selectedCore = n
				y1 = depth
				x2 = startx 

				if self.Constrained == 1 :
					predata = self.SpliceTieData[self.SPselectedTie - 1]
					for prer in predata :
						x, y, n, f, startx, m, d, splicex, i, mode = prer 
						predata.remove(prer)
						newtag = x, pos[1], n, f, startx, m, depth , self.splicerX, i, mode
						predata.insert(0, newtag) 
					y2 = y1
					x1 = startx 
					self.guideSPCore = n
				elif self.Constrained == 0 :
					predata = self.SpliceTieData[self.SPselectedTie - 1]
					y2 = 0
					for prer in predata :
						x, y, n, f, startx, m, d, splicex, i, mode = prer 
						y2 = d

					x1 = startx 
					self.guideSPCore = n
					shift = y2 - depth 
					depth = y2

				self.spliceDepth = depth 

			reversed = False
			tempCore = -1
			if x2 < x1 :
				reversed = True
				tempCore = self.guideSPCore
				self.guideSPCore = self.selectedCore
				self.selectedCore = tempCore

			holeA = '-'
			holeB = '-'
			coreA = -1
			coreB = -1
			count = 0
			typeA = ''
			typeB = ''
			for s in self.DrawData["CoreInfo"]:
				data = s
				for r in data:
					if r[0] == self.selectedCore :
					 holeA = r[3]
					 coreA = r[4]
					 typeA = r[10]
					 count = count + 1
					if r[0] == self.guideSPCore :
					 holeB = r[3]
					 coreB = r[4]
					 typeB = r[10]
					 count = count + 1
					if count >= 2:
					 break
				if count >= 2 :
					break

			flag = self.parent.showELDPanel | self.parent.showCompositePanel | self.parent.showSplicePanel
			if holeA != '-' and holeB != '-' and flag == 1 :
				testret = py_correlator.evalcoef_splice(typeA, holeA, int(coreA), y1, y2)
				if testret != "" :
					if self.Constrained == 0 :
						shift = y2 - y1
						self.parent.splicePanel.OnUpdateDepth(shift)
					self.parent.OnAddFirstGraph(testret, y2, y1)

				for data_item in self.range :
					if data_item[0] == "Natural Gamma" and typeA == "NaturalGamma" :
						typeA = "Natural Gamma"
					elif data_item[0] == "NaturalGamma" and typeA == "Natural Gamma" :
						typeA = "NaturalGamma"
					if data_item[0] != typeA and data_item[0] != "splice" and data_item[0] != "log" :
						testret = py_correlator.evalcoef_splice(data_item[0], holeA, int(coreA), y1, y2)
						if testret != "" :
							self.parent.OnAddGraph(testret, y2, y1)
				self.parent.OnUpdateGraph()

			self.SPGuideCore = []
			if reversed == False :
				self.OnUpdateSPGuideData(self.selectedCore, depth, shift)
			else :
				self.OnUpdateSPGuideData(tempCore, depth, shift)
			got = 1

		if self.LogselectedTie >= 0 :

			logtieNo = self.LogselectedTie
			if (self.LogselectedTie % 2) == 0 : 
				logtieNo = self.LogselectedTie + 1 

			logtieSize = len(self.LogTieData) - 1
			if logtieNo <= logtieSize :
				data = self.LogTieData[logtieNo]
				depth = 0
				shift = 0
				y1 = 0
				y2 = 0
				x1 = 0
				x2 = 0
				for r in data :
					x, y, n, f, startx, m, d, splicex, i, raw = r
					depth = (pos[1] - self.startDepth) / (self.length / self.gap) + self.SPrulerStartDepth
					newtag = (x, pos[1], n, f, startx, m, depth, self.splicerX, i, depth)
					data.remove(r)
					data.insert(0, newtag)
					self.LogselectedCore = n
					y1 = depth
					x1 = x

				predata = self.LogTieData[logtieNo - 1]
				y2 = 0
				n = -1 
				tieNo = -1
				for prer in predata :
					x, y, n, f, startx, m, d, splicex, i, raw = prer
					tieNo = i 
					#y2 = (y - self.startDepth) / ( self.length / self.gap )+ self.SPrulerStartDepth
					y2 = d
					x2 = x
				shift = y2 - depth
				depth = y2

				if x1 < x2 :
					temp = y1
					y1 = y2
					y2 = temp
					temp = self.LogselectedCore
					self.LogselectedCore = n
					n = temp

				self.saganDepth = y2 

				holenoA = '-'
				corenoA = -1
				count = 0
				for s in self.DrawData["CoreInfo"]:
					data = s
					for r in data:
						if r[0] == n :
							holenoA = r[3]
							corenoA = r[4]
							count = count + 1
						if count >= 1:
							break
					if count >= 1 :
						break

				self.PreviewLog = [-1, -1, 1.0, 0, -1, -1, 1.0]
				if logtieNo == 1 :
					self.PreviewLog[3] = y1 - y2
					y3 = 0
					self.PreviewLog[2] = (y1 - y3) / (y2 - y3)
					self.PreviewLog[0] = y3
					self.PreviewLog[1] = y2

					if (logtieNo + 2) < len(self.LogTieData) :
						data = self.LogTieData[logtieNo + 1]
						for r in data :
							y3 = r[6]

						self.PreviewLog[4] = y2
						self.PreviewLog[5] = y3
						self.PreviewLog[6] = (y3 - y1) / (y3 - y2)
				elif len(self.LogTieData) == 2 or self.PreviewNumTies == 0 or self.PreviewFirstNo == logtieNo:
					self.PreviewLog[3] = y1 - y2
					if self.Floating == False :
						self.PreviewLog[0] = self.FirstDepth
						self.PreviewLog[1] = y2
						self.PreviewLog[2] = (y1 - self.FirstDepth) / (y2 - self.FirstDepth)

						if (logtieNo + 2) < len(self.LogTieData) :
							data = self.LogTieData[logtieNo + 1]
							for r in data :
								y3 = r[6]

							self.PreviewLog[4] = y2
							self.PreviewLog[5] = y3
							self.PreviewLog[6] = (y3 - y1) / (y3 - y2)
				else :
					y3 = 0
					data = self.LogTieData[logtieNo - 2]
					for r in data :
						y3 = r[6]
					self.PreviewLog[2] = (y1 - y3) / (y2 - y3)
					self.PreviewLog[0] = y3
					self.PreviewLog[1] = y2

					if (logtieNo + 2) < len(self.LogTieData) :
						data = self.LogTieData[logtieNo + 1]
						for r in data :
							y3 = r[6]

						self.PreviewLog[4] = y2
						self.PreviewLog[5] = y3
						self.PreviewLog[6] = (y3 - y1) / (y3 - y2)

				flag = self.parent.showELDPanel | self.parent.showCompositePanel | self.parent.showSplicePanel
				if holenoA != '-' and flag == 1 :
					testret = py_correlator.evalcoefLog(holenoA, int(corenoA), y2, y1)
					if testret != "" :
						self.parent.OnAddFirstGraph(testret, y2, y1)
						self.parent.OnUpdateGraph()
				got = 1


		if self.selectScroll == 1 and self.grabScrollA == 0 and self.grabScrollC == 0 :
			if pos[0] >= 180 and pos[0] <= (self.Width - 100):
				scroll_widthA = self.splicerX - (self.startDepth * 2.3) - self.compositeX 
				scroll_widthB = self.Width - (self.startDepth * 1.6) - self.splicerX 
				temp_splicex = self.splicerX
				self.splicerX = pos[0]

				bmp, x, y = self.DrawData["HScroll"]
				scroll_rate = (x - self.compositeX) / (scroll_widthA * 1.0)
				scroll_widthA = self.splicerX - (self.startDepth * 2.3) - self.compositeX 
				scroll_x = scroll_widthA * scroll_rate
				scroll_x += self.compositeX
				self.DrawData["HScroll"] = (bmp, scroll_x, y)

		if got == 0:
			self.DrawData["MouseInfo"] = [] 
			self.selectedCore = -1 

		self.UpdateDrawing()

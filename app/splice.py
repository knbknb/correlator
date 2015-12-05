'''
Created on Nov 16, 2015

@author: bgrivna

Support for the creation and editing of Splice Interval Tables.
'''

import unittest

import pandas

import tabularImport

# drawing constants
TIE_CIRCLE_RADIUS = 8


class Interval:
    def __init__(self, top, bot):
        if top >= bot:
            raise ValueError("Cannot create Interval: top must be < bot")
        self.top = top
        self.bot = bot
        
    def __repr__(self):
        return "[{} - {}]".format(self.top, self.bot)
    
    def valid(self):
        return self.top < self.bot
    
    def contains(self, val):
        return contains(self, val)
    
    def containsStrict(self, val):
        return containsStrict(self, val)
    
    def equals(self, interval):
        return self.top == interval.top and self.bot == interval.bot
    
    def length(self):
        return self.bot - self.top
    
    def overlaps(self, interval):
        return overlaps(self, interval)
    
    def touches(self, interval):
        return touches(self, interval)
    
    def encompasses(self, interval):
        return self.top <= interval.top and self.bot >= interval.bot

# "Touching" intervals have a common edge but no overlap...this means
# that an Interval does *not* touch itself.
def touches(i1, i2):
    return i1.top == i2.bot or i1.bot == i2.top

# Do Intervals overlap? "Touching" intervals (i1.bot == i2.top)
# are considered to overlap as well. Need to check both to cover
# case where one interval encompasses another
def overlaps(i1, i2):
    return i1.contains(i2.top) or i1.contains(i2.bot) or i2.contains(i1.top) or i2.contains(i1.bot)

# Does Interval i contain value val (top and bot inclusive)?
def contains(interval, val): 
    return val <= interval.bot and val >= interval.top

# Does Interval i contain value val (top and bot excluded)?
def containsStrict(interval, val):
    return val < interval.bot and val > interval.top

# Combine overlapping Intervals i1 and i2, return resulting Interval
def merge(i1 ,i2):
    if not i1.overlaps(i2):
        raise ValueError("Can't merge non-overlapping intervals {} and {}".format(i1, i2))
    return Interval(min(i1.top, i2.top), max(i1.bot, i2.bot))

# Given list of Intervals, merge where possible and return resulting Intervals.
# TODO: default param to sort or not?
def union(intervals):
    intervals = sorted(intervals, key=lambda i: i.top) #  must be top-sorted
    result = []
    lastMergeIdx = -1
    for i in range(len(intervals)):
        if i <= lastMergeIdx: # skip already-merged intervals from subloop
            continue
        newint = intervals[i]
        if i == len(intervals) - 1: # last interval
            result.append(newint)
        else: # merge as many subsequent Intervals into newint as possible, then append to result list
            for j in range(i+1, len(intervals)): 
                if newint.overlaps(intervals[j]): # can we merge this interval into newint?
                    newint = merge(newint, intervals[j])
                    lastMergeIdx = j
                    if j == len(intervals) - 1: # last interval
                        result.append(newint)
                else:
                    result.append(newint)
                    break
    return result

# Return list of Intervals of any gaps within overall range of passed Intervals
def gaps(intervals, mindepth, maxdepth):
    result = []
    if len(intervals) == 0:
        result.append(Interval(mindepth, maxdepth))
    else:
        intervals = union(intervals)
        
        # gaps between min/max and start/end of intervals range
        intmin = min([i.top for i in intervals])
        intmax = max([i.bot for i in intervals])
        if mindepth < intmin:
            result.append(Interval(mindepth, intmin))
        if maxdepth > intmax:
            result.append(Interval(intmax, maxdepth))
    
        # gaps within intervals
        if len(intervals) > 1:
            for i in range(len(intervals) - 1):
                gap = Interval(intervals[i].bot, intervals[i+1].top)
                result.append(gap)
    return result


class TestIntervals(unittest.TestCase):
    def test_create(self):
        with self.assertRaises(ValueError):
            Interval(1, 1) # top == bot
        with self.assertRaises(ValueError):
            Interval(1, 0) # top > bot
        i = Interval(-1, 3.1415)
        self.assertEquals(i.top, -1)
        self.assertEquals(i.bot, 3.1415)
        
    def test_touches(self):
        i1 = Interval(0, 10)
        i2 = Interval(10, 20)
        self.assertTrue(i1.touches(i2))
        self.assertTrue(i2.touches(i1))
        self.assertFalse(i1.touches(i1))
        
    def test_contains(self):
        i = Interval(0, 10)
        self.assertTrue(i.contains(0))
        self.assertTrue(i.contains(10))
        self.assertFalse(i.containsStrict(0))
        self.assertFalse(i.containsStrict(10))
        self.assertTrue(i.contains(5))
        self.assertFalse(i.contains(-0.0001))
        self.assertFalse(i.contains(10.0001))
        
    def test_overlaps(self):
        i1 = Interval(0, 10)
        i2 = Interval(5, 15)
        i3 = Interval(10, 20)
        i4 = Interval(20.0001, 30)
        i5 = Interval(-10, 40) # all-encompassing
        self.assertTrue(i1.overlaps(i1))
        self.assertTrue(i1.overlaps(i2))
        self.assertTrue(i1.overlaps(i3))
        self.assertTrue(i2.overlaps(i3))
        self.assertFalse(i3.overlaps(i4))
        self.assertTrue(i5.overlaps(i1))
        self.assertTrue(i1.overlaps(i5))
        
    def test_merge(self):
        i1 = Interval(0, 10)
        i2 = Interval(10, 20)
        i3 = Interval(20, 30)
        i4 = Interval(5, 15)
        
        merge1 = merge(i1, i2)
        self.assertTrue(merge1.top == 0)
        self.assertTrue(merge1.bot == 20)
        
        merge2 = merge(i3, merge1)
        self.assertTrue(merge2.top == 0)
        self.assertTrue(merge2.bot == 30)
        
        merge3 = merge(i1, i4)
        self.assertTrue(merge3.top == 0)
        self.assertTrue(merge3.bot == 15)
        
        with self.assertRaises(ValueError):
            merge(i1, i3)
            
    def test_union(self):
        i1 = Interval(0, 10)
        i2 = Interval(5, 15)
        i3 = Interval(10, 20)
        i4 = Interval(21, 25)
        i5 = Interval(24, 25)
        
        u1 = union([i1, i2])
        self.assertTrue(len(u1) == 1)
        self.assertTrue(u1[0].top == 0)
        self.assertTrue(u1[0].bot == 15)
        
        u2 = union([i1, i2, i3])
        self.assertTrue(len(u2) == 1)
        self.assertTrue(u2[0].top == 0)
        self.assertTrue(u2[0].bot == 20)
        
        u3 = union([i3, i4, i5])
        self.assertTrue(len(u3) == 2)
        self.assertTrue(u3[0].top == 10)
        self.assertTrue(u3[1].top == 21)
        self.assertTrue(u3[1].bot == 25)
        
        u4 = union([Interval(0, 1), Interval(0, 1)])
        self.assertTrue(u4[0].top == 0)
        self.assertTrue(u4[0].bot == 1)
        
        u5 = union([Interval(2, 3), Interval(1, 4)])
        self.assertTrue(len(u5) == 1)
        self.assertTrue(u5[0].top == 1)
        self.assertTrue(u5[0].bot == 4)


class SpliceInterval:
    def __init__(self, coreinfo, top, bot, comment=""):
        self.coreinfo = coreinfo # CoreInfo for core used in this interval
        self.interval = Interval(top, bot)
        self.comment = comment
        
    def valid(self):
        return self.interval.valid()

    # 11/18/2015 brg: name getTop/Bot() to avoid Python's silence when one
    # mistakenly uses SpliceInterval.top instead of top(). Confusing since
    # Interval.top/bot is legitimate. 
    def getTop(self): # depth of top
        return self.interval.top
    
    def getBot(self): # depth of bot
        return self.interval.bot
    
    def setTop(self, depth):
        self.interval.top = depth
        
    def setBot(self, depth):
        self.interval.bot = depth
        
    def coreTop(self): # minimum depth of core
        return self.coreinfo.minDepth
    
    def coreBot(self): # maximum depth of core
        return self.coreinfo.maxDepth
    
    def overlaps(self, interval):
        return self.interval.overlaps(interval)
    
    def contains(self, value):
        return self.interval.contains(value)
    
    def getHoleCoreStr(self):
        return self.coreinfo.getHoleCoreStr()
    
    def __repr__(self):
        return str(self.interval)


def clampBot(spliceInterval, depth, returnMessage=False):
    msg = ""
    hcstr = spliceInterval.getHoleCoreStr()
    if depth > spliceInterval.coreBot():
        msg = "Bottom of core {}".format(hcstr)
        depth = spliceInterval.coreBot()
    if depth < spliceInterval.getTop() or depth < spliceInterval.coreTop():
        depth = max([spliceInterval.getBot(), spliceInterval.coreTop()])
        if spliceInterval.coreTop() >= spliceInterval.getTop():
            msg = "Top of core {}".format(hcstr)
        else:
            msg = "Top of interval {}".format(hcstr)
    if returnMessage:
        return depth, msg
    else:
        return depth

def clampTop(spliceInterval, depth, returnMessage=False):
    msg =""
    hcstr = spliceInterval.getHoleCoreStr()
    if depth < spliceInterval.coreTop():
        msg = "Top of core {}".format(hcstr)
        depth = spliceInterval.coreTop()
    if depth > spliceInterval.getBot() or depth > spliceInterval.coreBot():
        depth = min([spliceInterval.getBot(), spliceInterval.coreBot()])
        if spliceInterval.coreBot() <= spliceInterval.getBot():
            msg = "Bottom of core {}".format(hcstr)
        else:
            msg = "Top of interval {}".format(hcstr)
    if returnMessage:
        return depth, msg
    else:
        return depth

class SpliceIntervalTie():
    def __init__(self, interval, adjInterval):
        self.interval = interval
        self.adjInterval = adjInterval
        self.clampMessage = ""

    def _setClampMessage(self, message):
        self.clampMessage = message
        
    def getButtonName(self):
        cores = sorted([self.interval, self.adjInterval], key=lambda i:i.getTop())
        return "{} && {}".format(cores[0].getHoleCoreStr(), cores[1].getHoleCoreStr())


class SpliceIntervalTopTie(SpliceIntervalTie):
    def __init__(self, interval, adjInterval):
        SpliceIntervalTie.__init__(self, interval, adjInterval)
        
    def getName(self): # text to display on tie
        name = ""
        if self.isTied(): # list topmost core first
            cores = sorted([self.interval, self.adjInterval], key=lambda i:i.getTop())
            name = "Tie: {} & {}".format(cores[0].getHoleCoreStr(), cores[1].getHoleCoreStr())
        else:
            name = self.interval.coreinfo.getHoleCoreStr() + " top"
        return name
        
    def isTied(self):
        return self.adjInterval is not None and self.interval.getTop() == self.adjInterval.getBot()
    
    def canTie(self):
        result = False
        if self.adjInterval is not None:
            diff = self.interval.getTop() - self.adjInterval.getBot()
            result = round(diff,3) <= 0.001 and diff > 0
        return result

    def tie(self):
        if self.canTie():
            self.interval.setTop(self.adjInterval.getBot())
            
    def split(self):
        if self.isTied():
            self.interval.setTop(self.adjInterval.getBot() + 0.001)
    
    def depth(self):
        return self.interval.getTop()
        
    def move(self, depth):
        depth = self.clampTieTop(depth)
        # isTied() is based on equality of interval top/bot and adjInterval bot/top, check before changing depth!
        if self.isTied():
            self._moveAdj(depth)
        self.interval.setTop(depth)
        
    def _moveAdj(self, depth):
        self.adjInterval.setBot(depth)
    
    def clampTieTop(self, depth):
        depth, msg = clampTop(self.interval, depth, True)
        self._setClampMessage(msg)
        if self.isTied():
            depth, msg = clampBot(self.adjInterval, depth, True)
            if len(msg) > 0:
                self._setClampMessage(msg)
        elif self.adjInterval is not None and depth <= self.adjInterval.getBot():
            depth = self.adjInterval.getBot() + 0.001 # one mm to prevent equality
            self._setClampMessage("Bottom of interval {}".format(self.adjInterval.getHoleCoreStr()))
        return depth
    
class SpliceIntervalBotTie(SpliceIntervalTie):
    def __init__(self, interval, adjInterval):
        SpliceIntervalTie.__init__(self, interval, adjInterval)
        
    def getName(self): # text to display on tie
        name = ""
        if self.isTied(): # list topmost core first
            cores = sorted([self.interval, self.adjInterval], key=lambda i:i.getTop())
            name = "Tie: {} & {}".format(cores[0].getHoleCoreStr(), cores[1].getHoleCoreStr())
        else:
            name = self.interval.coreinfo.getHoleCoreStr() + " bottom"
        return name
    
    def isTied(self):
        return self.adjInterval is not None and self.interval.getBot() == self.adjInterval.getTop()

    def canTie(self):
        result = False
        if self.adjInterval is not None:
            diff = self.adjInterval.getTop() - self.interval.getBot()
            result = round(diff, 3) <= 0.001 and diff > 0
        return result
    
    def tie(self):
        if self.canTie():
            self.interval.setBot(self.adjInterval.getTop())
            
    def split(self):
        if self.isTied():
            self.interval.setBot(self.adjInterval.getTop() - 0.001)
    
    def depth(self):
        return self.interval.getBot()
    
    def move(self, depth):
        depth = self.clampTieBot(depth)
        # isTied() is based on equality of interval top/bot and adjInterval bot/top, check before changing depth!
        if self.isTied():
            self._moveAdj(depth)
        self.interval.setBot(depth)
        
    def _moveAdj(self, depth):
        self.adjInterval.setTop(depth)
    
    def clampTieBot(self, depth):
        depth, msg = clampBot(self.interval, depth, True)
        self._setClampMessage(msg)
        if self.isTied():
            depth, msg = clampTop(self.adjInterval, depth, True)
            if len(msg) > 0:
                self._setClampMessage(msg)
        elif self.adjInterval is not None and depth >= self.adjInterval.getTop():
            depth = self.adjInterval.getTop() - 0.001 # one mm to prevent equality
            self._setClampMessage("Top of interval {}".format(self.adjInterval.getHoleCoreStr()))
        return depth


class SpliceManager:
    def __init__(self, parent):
        self.parent = parent # using to access sectionSummary and HoleData for now
        self.selChangeListeners = []
        self.addIntervalListeners = []
        self.clear()
        
    def clear(self): # initialize data members
        self.ints = [] # list of SpliceIntervals ordered by top member
        self.filepath = None
        self.selected = None # currently selected SpliceInterval
        self.topTie = None
        self.botTie = None
        self.selectedTie = None
        self.dirty = False # need save?
        self.errorMsg = "Init State: No errors here, everything is peachy!"        
        
        self._onAdd(False) # notify listeners so UI elements update
    
    def count(self):
        return len(self.ints)
        
    def getIntervalsInRange(self, mindepth, maxdepth):
        result = []
        if mindepth < maxdepth:
            testInterval = Interval(mindepth, maxdepth)
            result = [i for i in self.ints if i.overlaps(testInterval)]
        else:
            print "Bogus search range: mindepth = {}, maxdepth = {}".format(mindepth, maxdepth)
        return result
    
    def getIntervalAtDepth(self, depth):
        result = None
        for interval in self.ints:
            if interval.contains(depth):
                result = interval
                break
        return result
    
    def getIntervalAtIndex(self, index):
        if index < len(self.ints):
            return self.ints[index]
        
    def getDataTypes(self):
        types = set()
        for interval in self.ints:
            types.add(interval.coreinfo.type)
        return types
    
    def hasSelection(self):
        return self.selected is not None

    def _canDeselect(self):
        result = True
        if self.hasSelection():
            result = self.selected.valid()
        return result
    
    def _updateSelection(self, interval):
        if (interval != self.selected):
            self.selected = interval
            self._updateTies()
            self._onSelChange()
            
    # SpliceController that serves as intermediary between SpliceManager model and client views?
    def save(self, filepath): # better in Data Manager? creating a dependency on MainFrame is not desirable.
        # better to create dependencies on SectionSummary and a non-existent "HoleDatabase" class, though
        # HoleData will do...though we only need it for affine stuff, so possibly an AffineManager?
        print "Saving splice to {}".format(filepath)
        
        rows = []
        
        secsumm = self.parent.sectionSummary
        #print str(secsumm.dataframe)
        #print "\n##############################\n"
        
        for index, si in enumerate(self.ints):
            site = si.coreinfo.leg # ugh...mixed up? this site-exp shit is so dumb.
            hole = si.coreinfo.hole
            core = si.coreinfo.holeCore
            #print "Saving Interval {}: {}".format(index, si.coreinfo.getHoleCoreStr())
            
            offset = self.parent.Window.findCoreAffineOffset(hole, core)
            #print "   affine offset = {}".format(si.coreinfo.getHoleCoreStr(), offset)
         
            # section summary is always in CSF-A, remove CCSF-A/MCD offset for calculations
            mbsfTop = round(si.getTop(), 3) - offset
            topSection = secsumm.getSectionAtDepth(site, hole, core, mbsfTop)
            if topSection is not None:
                topDepth = secsumm.getSectionTop(site, hole, core, topSection)
                topOffset = round((mbsfTop - topDepth) * 100.0, 1) # section depth in cm
            else:
                print "Skipping, couldn't find top section at top CSF depth {}".format(mbsfTop)
                continue
            
            mbsfBot = round(si.getBot(), 3) - offset
            botSection = secsumm.getSectionAtDepth(site, hole, core, mbsfBot)
            if botSection is not None:
                # bottom offset is poorly named: from the interval's bottom depth, it is the
                # offset from the top (not bottom) of the containing section
                botDepth = secsumm.getSectionTop(site, hole, core, botSection)
                botOffset = round((mbsfBot - botDepth) * 100.0, 1) # section depth in cm
            else:
                print "Skipping, couldn't find section at bottom CSF depth {}".format(mbsfBot)
                continue
            
            coreType = secsumm.getSectionCoreType(site, hole, core, botSection)
            
            # stub out for now: type for each of top and bottom? "CORE" type per Peter B's request?
            spliceType = "APPEND"
            if index < len(self.ints) - 1:
                if self.ints[index+1].getTop() == si.getBot():
                    spliceType = "TIE"
                    
            #print "   topSection {}, offset {}, depth {}, mcdDepth {}\nbotSection {}, offset {}, depth {}, mcdDepth {}\ntype {}, data {}, comment {}".format(topSection, topOffset, mbsfTop, mbsfTop+offset, botSection, botOffset, mbsfBot, mbsfBot+offset, spliceType, si.coreinfo.type, si.comment)
            
            series = pandas.Series({'Exp':si.coreinfo.site, 'Site':site, 'Hole':hole, 'Core':core, 'CoreType':coreType, \
                                    'TopSection':topSection, 'TopOffset':topOffset, 'TopDepthCSF':mbsfTop, 'TopDepthCCSF':mbsfTop+offset, \
                                    'BottomSection':botSection, 'BottomOffset':botOffset, 'BottomDepthCSF':mbsfBot, 'BottomDepthCCSF':mbsfBot+offset, \
                                    'SpliceType':spliceType, 'DataUsed':si.coreinfo.type, 'Comment':si.comment})
            rows.append(series)            
        if len(rows) > 0:
            df = pandas.DataFrame(columns=tabularImport.SITFormat.req)
            df = df.append(rows, ignore_index=True)
            #print "{}".format(df)
            tabularImport.writeToFile(df, filepath)
            self.setDirty(False)
            
    def load(self, filepath):
        self.clear()
        df = tabularImport.readFile(filepath)
        for index, row in df.iterrows(): # itertuples() is faster if needed
            #print "Loading row {}: {}".format(index, str(row))
            # for each row, create CoreInfo
            #exp = row.Exp
            #site = row.Site
            hole = row.Hole
            core = str(row.Core)
            datatype = row.DataUsed
            coreinfo = self.parent.Window.findCoreInfoByHoleCoreType(hole, core, datatype)
            if coreinfo is None:
                #print "Couldn't find hole {} core {} of type {}".format(hole, core, datatype)
                coreinfo = self.parent.Window.findCoreInfoByHoleCore(hole, core)
                if coreinfo is None:
                    continue
            # todo: update with section summary values
            
            # set interval top and bottom (based on affine)
            affineOffset = self.parent.Window.findCoreAffineOffset(hole, core)
            coreinfo.minDepth += affineOffset
            coreinfo.maxDepth += affineOffset
            
            #print "affineOffset = {}".format(affineOffset)
            
            top = row.TopDepthCSF
            bot = row.BottomDepthCSF
            if top + affineOffset != row.TopDepthCCSF:
                print "table has top CSF = {}, CCSF = {} for an offset of {}, current affine offset = {}".format(top, row.TopDepthCCSF, row.TopDepthCCSF - top, affineOffset)
            if bot + affineOffset != row.BottomDepthCCSF:
                print "table has bottom CSF = {}, CCSF = {} for an offset of {}, current affine offset = {}".format(bot, row.BottomDepthCCSF, row.BottomDepthCCSF - top, affineOffset)
                
            spliceInterval = SpliceInterval(coreinfo, top + affineOffset, bot + affineOffset)
            self.ints.append(spliceInterval) # add to ints - should already be sorted properly
        
        self._onAdd(dirty=False) # notify listeners that intervals have been added

    def select(self, depth):
        good = False
        if self._canDeselect():
            good = True
            selInt = self.getIntervalAtDepth(depth)
            self._updateSelection(selInt)
        else:
            self._setErrorMsg("Can't deselect current interval, it has zero length. You may delete.")
        return good
    
    def selectByIndex(self, index):
        if self._canDeselect():
            if len(self.ints) > index:
                self._updateSelection(self.ints[index])
        else:
            self._setErrorMsg("Can't deselect current interval, it has zero length. You may delete.")

    def _setErrorMsg(self, msg):
        self.errorMsg = msg
        
    def getErrorMsg(self):
        return self.errorMsg
    
    def isDirty(self):
        return self.dirty

    def setDirty(self, dirty=True):
        self.dirty = dirty

    def getSelected(self):
        return self.selected
    
    def getSelectedIndex(self):
        return self.ints.index(self.selected) if self.hasSelection() else -1
    
    def deleteSelected(self):
        if self.selected in self.ints:
            self.ints.remove(self.selected)
            self.selected = None
            self.selectTie(None)
            self.setDirty()
            self._onSelChange()
            
    def selectTie(self, siTie):
        if siTie in self.getTies():
            self.selectedTie = siTie
        elif siTie is None:
            self.selectedTie = None
            
    def getSelectedTie(self):
        return self.selectedTie
    
    def getIntervalAbove(self, interval):
        result = None
        idx = self.ints.index(interval)
        if idx != -1 and idx > 0:
            result = self.ints[idx - 1]
        return result
    
    def getIntervalBelow(self, interval):
        result = None
        idx = self.ints.index(interval)
        if idx != -1 and idx < len(self.ints) - 1:
            result = self.ints[idx + 1]
        return result
    
    def getTies(self):
        result = []
        if self.topTie is not None and self.botTie is not None:
            result = [self.topTie, self.botTie]
        return result
    
    def add(self, coreinfo):
        interval = Interval(coreinfo.minDepth, coreinfo.maxDepth)
        if self._canAdd(interval):
            for gap in gaps(self._overs(interval), interval.top, interval.bot):
                self.ints.append(SpliceInterval(coreinfo, gap.top, gap.bot))
                self.ints = sorted(self.ints, key=lambda i: i.getTop())
                #print "Added {}, have {} splice intervals: = {}".format(interval, len(self.ints), self.ints)
            self._onAdd()
        else:
            print "couldn't add interval {}".format(interval)
            
    def addSelChangeListener(self, listener):
        if listener not in self.selChangeListeners:
            self.selChangeListeners.append(listener)
            
    def removeSelChangeListener(self, listener):
        if listener in self.selChangeListeners:
            self.selChangeListeners.remove(listener)
            
    def addAddIntervalListener(self, listener):
        if listener not in self.addIntervalListeners:
            self.addIntervalListeners.append(listener)
            
    def removeAddIntervalListener(self, listener):
        if listener in self.addIntervalListeners:
            self.addIntervalListeners.remove(listener)

    def _updateTies(self):
        if self.hasSelection():
            self.topTie = SpliceIntervalTopTie(self.selected, self.getIntervalAbove(self.selected))
            self.botTie = SpliceIntervalBotTie(self.selected, self.getIntervalBelow(self.selected))
        else:
            self.topTie = self.botTie = None
        
    def _canAdd(self, interval):
        u = union([i.interval for i in self.ints])
        e = [i for i in u if i.encompasses(interval)]
        if len(e) > 0:
            print "Interval {} encompassed by {}".format(interval, e)
        return len(e) == 0
    
    def _onAdd(self, dirty=True):
        self._updateTies()
        if dirty:
            self.setDirty()
        for listener in self.addIntervalListeners:
            listener()
    
    def _onSelChange(self):
        for listener in self.selChangeListeners:
            listener()

    # return union of all overlapping Intervals in self.ints    
    def _overs(self, interval):
        return union([i.interval for i in self.ints if i.interval.overlaps(interval)])
    
    
    
# run unit tests on main for now
if __name__ == '__main__':
    unittest.main()
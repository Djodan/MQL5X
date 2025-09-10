//+------------------------------------------------------------------+
//|                                                  TestingMode.mqh |
//|                     Testing hooks and utilities for MQL5X       |
//+------------------------------------------------------------------+
#ifndef MQL5X_TESTINGMODE_MQH
#define MQL5X_TESTINGMODE_MQH

#include "GlobalVariables.mqh"
// We rely on ticket-based helpers declared in Trades.mqh, which is included by MQL5X.mq5 before this file.

// Normalize a requested volume to the symbol's constraints
double TM_NormalizeVolume(string symbol, double vol)
{
   double minVol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double maxVol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double step   = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(step<=0.0) step = 0.01;
   // clamp
   if(vol < minVol) vol = minVol;
   if(vol > maxVol) vol = maxVol;
   // align to step (round down to be safe)
   double steps = MathFloor(vol/step);
   vol = steps*step;
   // avoid going to zero if min > 0
   if(vol < minVol) vol = minVol;
   return vol;
}

// Modify SL/TP to test values relative to open price
bool TM_ModifySLTP(string symbol, long type, double openPrice, ulong ticket)
{
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   if(point<=0) return false;
   int    digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   // simple +/- 50 points for test
   double sl=0.0, tp=0.0;
   if(type==POSITION_TYPE_BUY)
   {
      sl = NormalizeDouble(openPrice - 50*point, digits);
      tp = NormalizeDouble(openPrice + 50*point, digits);
   }
   else
   {
      sl = NormalizeDouble(openPrice + 50*point, digits);
      tp = NormalizeDouble(openPrice - 50*point, digits);
   }
   return ModifyPositionByTicket(ticket, sl, tp);
}

// Perform testing action when a new position is opened: modify SL/TP and half-close
void Testing_HandleOpenedPosition(ulong position_ticket)
{
   string symbol=""; long ptype=0; double pvol=0.0;
   if(!SelectPositionByTicket(position_ticket, symbol, ptype, pvol))
      return;
   double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);

   // Attempt to modify SL/TP (test values)
   TM_ModifySLTP(symbol, ptype, openPrice, position_ticket);

   // Close half the volume
   double half = TM_NormalizeVolume(symbol, pvol/2.0);
   // if normalization makes it equal to full volume, try to ensure we don't close 100% unintentionally
   if(half >= pvol && pvol > 0)
   {
      double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
      if(step>0 && pvol - step >= SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN))
         half = TM_NormalizeVolume(symbol, pvol - step);
   }
   if(half > 0.0 && half < pvol)
   {
      ClosePositionByTicket(position_ticket, half);
   }
}

// Called once at init when TestingMode is enabled
void Testing_OnInit()
{
   // Print("[Testing] Mode enabled.");
}

// Called on every tick when TestingMode is enabled
void Testing_OnTick()
{
   // Example: you can inject simulated actions here during testing
}

// Called on timer when TestingMode is enabled
void Testing_OnTimer()
{
   // Example: periodic test assertions or logs
}

#endif // MQL5X_TESTINGMODE_MQH

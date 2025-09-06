//+------------------------------------------------------------------+
//|                                                       Trades.mqh |
//|                Helpers to manage open/closed trade collections  |
//+------------------------------------------------------------------+
#ifndef MQL5X_TRADES_MQH
#define MQL5X_TRADES_MQH

#include "GlobalVariables.mqh"

// Utility: find index of open trade by ticket, -1 if not found
int FindOpenTradeIndexByTicket(ulong ticket)
{
   for(int i=0;i<ArraySize(openTickets);++i)
      if(openTickets[i]==ticket)
         return i;
   return -1;
}

// Utility: find index of closed trade by deal, -1 if not found
int FindClosedOfflineIndexByDeal(ulong deal)
{
   for(int i=0;i<ArraySize(closedOfflineDeals);++i)
      if(closedOfflineDeals[i]==deal)
         return i;
   return -1;
}

int FindClosedOnlineIndexByDeal(ulong deal)
{
   for(int i=0;i<ArraySize(closedOnlineDeals);++i)
      if(closedOnlineDeals[i]==deal)
         return i;
   return -1;
}

// Add or update an open trade entry
void UpsertOpenTrade(
   ulong ticket,
   string symbol,
   long type,
   double volume,
   double openPrice,
   double currentPrice,
   double sl,
   double tp,
   datetime openTime,
   long magic,
   string comment)
{
   int idx = FindOpenTradeIndexByTicket(ticket);
   if(idx<0)
   {
      int n = ArraySize(openTickets);
      ArrayResize(openTickets, n+1);
      ArrayResize(openSymbols, n+1);
      ArrayResize(openTypes, n+1);
      ArrayResize(openVolumes, n+1);
      ArrayResize(openOpenPrices, n+1);
      ArrayResize(openCurrentPrices, n+1);
      ArrayResize(openSLs, n+1);
      ArrayResize(openTPs, n+1);
      ArrayResize(openOpenTimes, n+1);
      ArrayResize(openMagics, n+1);
      ArrayResize(openComments, n+1);

      openTickets[n]      = ticket;
      openSymbols[n]      = symbol;
      openTypes[n]        = type;
      openVolumes[n]      = volume;
      openOpenPrices[n]   = openPrice;
      openCurrentPrices[n]= currentPrice;
      openSLs[n]          = sl;
      openTPs[n]          = tp;
      openOpenTimes[n]    = openTime;
      openMagics[n]       = magic;
      openComments[n]     = comment;
   }
   else
   {
      openTickets[idx]       = ticket;
      openSymbols[idx]       = symbol;
      openTypes[idx]         = type;
      openVolumes[idx]       = volume;
      openOpenPrices[idx]    = openPrice;
      openCurrentPrices[idx] = currentPrice;
      openSLs[idx]           = sl;
      openTPs[idx]           = tp;
      openOpenTimes[idx]     = openTime;
      openMagics[idx]        = magic;
      openComments[idx]      = comment;
   }
}

// Remove an open trade by ticket
bool RemoveOpenTrade(ulong ticket)
{
   int idx = FindOpenTradeIndexByTicket(ticket);
   if(idx<0) return false;
   int n = ArraySize(openTickets);
   if(idx < n-1)
   {
      ArrayCopy(openTickets, openTickets, idx, idx+1, n-idx-1);
      ArrayCopy(openSymbols, openSymbols, idx, idx+1, n-idx-1);
      ArrayCopy(openTypes, openTypes, idx, idx+1, n-idx-1);
      ArrayCopy(openVolumes, openVolumes, idx, idx+1, n-idx-1);
      ArrayCopy(openOpenPrices, openOpenPrices, idx, idx+1, n-idx-1);
      ArrayCopy(openCurrentPrices, openCurrentPrices, idx, idx+1, n-idx-1);
      ArrayCopy(openSLs, openSLs, idx, idx+1, n-idx-1);
      ArrayCopy(openTPs, openTPs, idx, idx+1, n-idx-1);
      ArrayCopy(openOpenTimes, openOpenTimes, idx, idx+1, n-idx-1);
      ArrayCopy(openMagics, openMagics, idx, idx+1, n-idx-1);
      ArrayCopy(openComments, openComments, idx, idx+1, n-idx-1);
   }
   ArrayResize(openTickets, n-1);
   ArrayResize(openSymbols, n-1);
   ArrayResize(openTypes, n-1);
   ArrayResize(openVolumes, n-1);
   ArrayResize(openOpenPrices, n-1);
   ArrayResize(openCurrentPrices, n-1);
   ArrayResize(openSLs, n-1);
   ArrayResize(openTPs, n-1);
   ArrayResize(openOpenTimes, n-1);
   ArrayResize(openMagics, n-1);
   ArrayResize(openComments, n-1);
   return true;
}

// Add or update a closed trade entry
void UpsertClosedOffline(
   ulong deal,
   string symbol,
   long type,
   double volume,
   double openPrice,
   double closePrice,
   double profit,
   double swap,
   double commission,
   datetime closeTime)
{
   int idx = FindClosedOfflineIndexByDeal(deal);
   if(idx<0)
   {
      int n = ArraySize(closedOfflineDeals);
      ArrayResize(closedOfflineDeals, n+1);
      ArrayResize(closedOfflineSymbols, n+1);
      ArrayResize(closedOfflineTypes, n+1);
      ArrayResize(closedOfflineVolumes, n+1);
      ArrayResize(closedOfflineOpenPrices, n+1);
      ArrayResize(closedOfflineClosePrices, n+1);
      ArrayResize(closedOfflineProfits, n+1);
      ArrayResize(closedOfflineSwaps, n+1);
      ArrayResize(closedOfflineCommissions, n+1);
      ArrayResize(closedOfflineCloseTimes, n+1);

      closedOfflineDeals[n]       = deal;
      closedOfflineSymbols[n]     = symbol;
      closedOfflineTypes[n]       = type;
      closedOfflineVolumes[n]     = volume;
      closedOfflineOpenPrices[n]  = openPrice;
      closedOfflineClosePrices[n] = closePrice;
      closedOfflineProfits[n]     = profit;
      closedOfflineSwaps[n]       = swap;
      closedOfflineCommissions[n] = commission;
      closedOfflineCloseTimes[n]  = closeTime;
   }
   else
   {
      closedOfflineDeals[idx]       = deal;
      closedOfflineSymbols[idx]     = symbol;
      closedOfflineTypes[idx]       = type;
      closedOfflineVolumes[idx]     = volume;
      closedOfflineOpenPrices[idx]  = openPrice;
      closedOfflineClosePrices[idx] = closePrice;
      closedOfflineProfits[idx]     = profit;
      closedOfflineSwaps[idx]       = swap;
      closedOfflineCommissions[idx] = commission;
      closedOfflineCloseTimes[idx]  = closeTime;
   }
}

// Remove a closed trade by deal
bool RemoveClosedOffline(ulong deal)
{
   int idx = FindClosedOfflineIndexByDeal(deal);
   if(idx<0) return false;
   int n = ArraySize(closedOfflineDeals);
   if(idx < n-1)
   {
      ArrayCopy(closedOfflineDeals, closedOfflineDeals, idx, idx+1, n-idx-1);
      ArrayCopy(closedOfflineSymbols, closedOfflineSymbols, idx, idx+1, n-idx-1);
      ArrayCopy(closedOfflineTypes, closedOfflineTypes, idx, idx+1, n-idx-1);
      ArrayCopy(closedOfflineVolumes, closedOfflineVolumes, idx, idx+1, n-idx-1);
      ArrayCopy(closedOfflineOpenPrices, closedOfflineOpenPrices, idx, idx+1, n-idx-1);
      ArrayCopy(closedOfflineClosePrices, closedOfflineClosePrices, idx, idx+1, n-idx-1);
      ArrayCopy(closedOfflineProfits, closedOfflineProfits, idx, idx+1, n-idx-1);
      ArrayCopy(closedOfflineSwaps, closedOfflineSwaps, idx, idx+1, n-idx-1);
      ArrayCopy(closedOfflineCommissions, closedOfflineCommissions, idx, idx+1, n-idx-1);
      ArrayCopy(closedOfflineCloseTimes, closedOfflineCloseTimes, idx, idx+1, n-idx-1);
   }
   ArrayResize(closedOfflineDeals, n-1);
   ArrayResize(closedOfflineSymbols, n-1);
   ArrayResize(closedOfflineTypes, n-1);
   ArrayResize(closedOfflineVolumes, n-1);
   ArrayResize(closedOfflineOpenPrices, n-1);
   ArrayResize(closedOfflineClosePrices, n-1);
   ArrayResize(closedOfflineProfits, n-1);
   ArrayResize(closedOfflineSwaps, n-1);
   ArrayResize(closedOfflineCommissions, n-1);
   ArrayResize(closedOfflineCloseTimes, n-1);
   return true;
}

// Sync openTrades[] with current terminal positions
void SyncOpenTradesFromTerminal()
{
   // reset all open arrays in sync
   ArrayResize(openTickets,0);
   ArrayResize(openSymbols,0);
   ArrayResize(openTypes,0);
   ArrayResize(openVolumes,0);
   ArrayResize(openOpenPrices,0);
   ArrayResize(openCurrentPrices,0);
   ArrayResize(openSLs,0);
   ArrayResize(openTPs,0);
   ArrayResize(openOpenTimes,0);
   ArrayResize(openMagics,0);
   ArrayResize(openComments,0);
   int total = PositionsTotal();
   for(int i=0;i<total;++i)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket==0) continue;
      if(!PositionSelectByTicket(ticket))
         continue;
      UpsertOpenTrade(
         (ulong)PositionGetInteger(POSITION_TICKET),
         PositionGetString(POSITION_SYMBOL),
         PositionGetInteger(POSITION_TYPE),
         PositionGetDouble(POSITION_VOLUME),
         PositionGetDouble(POSITION_PRICE_OPEN),
         PositionGetDouble(POSITION_PRICE_CURRENT),
         PositionGetDouble(POSITION_SL),
         PositionGetDouble(POSITION_TP),
         (datetime)PositionGetInteger(POSITION_TIME),
         PositionGetInteger(POSITION_MAGIC),
         PositionGetString(POSITION_COMMENT)
      );
   }
}

// Append recently closed deals to closedTrades[] (limited by maxToScan)
void CollectRecentClosedDeals(int maxToScan=50)
{
   // Select history for a reasonable lookback (e.g., last 7 days)
   datetime from = TimeCurrent() - 7*24*60*60;
   if(!HistorySelect(from, TimeCurrent()))
      return;

   int totalDeals = HistoryDealsTotal();
   int startIdx = MathMax(0, totalDeals - maxToScan);
   for(int i=startIdx; i<totalDeals; ++i)
   {
      ulong deal = HistoryDealGetTicket(i);
      if(deal==0) continue;
      long reason = HistoryDealGetInteger(deal, DEAL_REASON);
      // consider only closing deals
      long entry = HistoryDealGetInteger(deal, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT) continue;

      // Try to fetch corresponding open price from history if available (not always)
      double openPrice = 0.0;

      UpsertClosedOffline(
         deal,
         HistoryDealGetString(deal, DEAL_SYMBOL),
         HistoryDealGetInteger(deal, DEAL_TYPE),
         HistoryDealGetDouble(deal, DEAL_VOLUME),
         openPrice,
         HistoryDealGetDouble(deal, DEAL_PRICE),
         HistoryDealGetDouble(deal, DEAL_PROFIT),
         HistoryDealGetDouble(deal, DEAL_SWAP),
         HistoryDealGetDouble(deal, DEAL_COMMISSION),
         (datetime)HistoryDealGetInteger(deal, DEAL_TIME)
      );
   }
}

// Add an online closed trade (from OnTradeTransaction)
void AddClosedOnline(
   ulong deal,
   string symbol,
   long type,
   double volume,
   double openPrice,
   double closePrice,
   double profit,
   double swap,
   double commission,
   datetime closeTime)
{
   int idx = FindClosedOnlineIndexByDeal(deal);
   if(idx<0)
   {
      int n = ArraySize(closedOnlineDeals);
      ArrayResize(closedOnlineDeals, n+1);
      ArrayResize(closedOnlineSymbols, n+1);
      ArrayResize(closedOnlineTypes, n+1);
      ArrayResize(closedOnlineVolumes, n+1);
      ArrayResize(closedOnlineOpenPrices, n+1);
      ArrayResize(closedOnlineClosePrices, n+1);
      ArrayResize(closedOnlineProfits, n+1);
      ArrayResize(closedOnlineSwaps, n+1);
      ArrayResize(closedOnlineCommissions, n+1);
      ArrayResize(closedOnlineCloseTimes, n+1);

      closedOnlineDeals[n]       = deal;
      closedOnlineSymbols[n]     = symbol;
      closedOnlineTypes[n]       = type;
      closedOnlineVolumes[n]     = volume;
      closedOnlineOpenPrices[n]  = openPrice;
      closedOnlineClosePrices[n] = closePrice;
      closedOnlineProfits[n]     = profit;
      closedOnlineSwaps[n]       = swap;
      closedOnlineCommissions[n] = commission;
      closedOnlineCloseTimes[n]  = closeTime;
   }
   else
   {
      closedOnlineDeals[idx]       = deal;
      closedOnlineSymbols[idx]     = symbol;
      closedOnlineTypes[idx]       = type;
      closedOnlineVolumes[idx]     = volume;
      closedOnlineOpenPrices[idx]  = openPrice;
      closedOnlineClosePrices[idx] = closePrice;
      closedOnlineProfits[idx]     = profit;
      closedOnlineSwaps[idx]       = swap;
      closedOnlineCommissions[idx] = commission;
      closedOnlineCloseTimes[idx]  = closeTime;
   }
}

#endif // MQL5X_TRADES_MQH

//+------------------------------------------------------------------+
//| Utilities: operate by exact position ticket                     |
//+------------------------------------------------------------------+

// Find and select a position by ticket (fallback via scan)
bool SelectPositionByTicket(ulong ticket, string &symbol, long &type, double &volume)
{
   if(!PositionSelectByTicket(ticket))
      return false;
   symbol = PositionGetString(POSITION_SYMBOL);
   type   = PositionGetInteger(POSITION_TYPE);
   volume = PositionGetDouble(POSITION_VOLUME);
   return true;
}

// Close a specific position by ticket (optionally partial volume)
bool ClosePositionByTicket(ulong ticket, double volume=0.0, uint deviation=20)
{
   string symbol=""; long ptype=0; double pvol=0.0;
   if(!SelectPositionByTicket(ticket, symbol, ptype, pvol))
      return false;

   if(volume<=0.0 || volume>pvol)
      volume = pvol;

   MqlTradeRequest req; MqlTradeResult res; ZeroMemory(req); ZeroMemory(res);
   req.action   = TRADE_ACTION_DEAL;
   req.symbol   = symbol;
   req.position = ticket;
   req.volume   = volume;
   req.deviation= (int)deviation;
   req.type_filling = ORDER_FILLING_FOK;

   double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
   if(ptype==POSITION_TYPE_BUY)
   {
      req.type  = ORDER_TYPE_SELL;   // close buy by selling
      req.price = bid;
   }
   else
   {
      req.type  = ORDER_TYPE_BUY;    // close sell by buying
      req.price = ask;
   }

   if(!OrderSend(req,res))
      return false;
   return (res.retcode==TRADE_RETCODE_DONE || res.retcode==TRADE_RETCODE_PLACED);
}

// Modify SL/TP for a specific position by ticket
bool ModifyPositionByTicket(ulong ticket, double sl, double tp)
{
   string symbol=""; long ptype=0; double pvol=0.0;
   if(!SelectPositionByTicket(ticket, symbol, ptype, pvol))
      return false;

   MqlTradeRequest req; MqlTradeResult res; ZeroMemory(req); ZeroMemory(res);
   req.action   = TRADE_ACTION_SLTP;
   req.symbol   = symbol;
   req.position = ticket;
   req.sl       = sl;
   req.tp       = tp;
   if(!OrderSend(req,res))
      return false;
   return (res.retcode==TRADE_RETCODE_DONE);
}


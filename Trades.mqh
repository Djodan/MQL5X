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
int FindClosedTradeIndexByDeal(ulong deal)
{
   for(int i=0;i<ArraySize(closedDeals);++i)
      if(closedDeals[i]==deal)
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
void UpsertClosedTrade(
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
   int idx = FindClosedTradeIndexByDeal(deal);
   if(idx<0)
   {
      int n = ArraySize(closedDeals);
      ArrayResize(closedDeals, n+1);
      ArrayResize(closedSymbols, n+1);
      ArrayResize(closedTypes, n+1);
      ArrayResize(closedVolumes, n+1);
      ArrayResize(closedOpenPrices, n+1);
      ArrayResize(closedClosePrices, n+1);
      ArrayResize(closedProfits, n+1);
      ArrayResize(closedSwaps, n+1);
      ArrayResize(closedCommissions, n+1);
      ArrayResize(closedCloseTimes, n+1);

      closedDeals[n]       = deal;
      closedSymbols[n]     = symbol;
      closedTypes[n]       = type;
      closedVolumes[n]     = volume;
      closedOpenPrices[n]  = openPrice;
      closedClosePrices[n] = closePrice;
      closedProfits[n]     = profit;
      closedSwaps[n]       = swap;
      closedCommissions[n] = commission;
      closedCloseTimes[n]  = closeTime;
   }
   else
   {
      closedDeals[idx]       = deal;
      closedSymbols[idx]     = symbol;
      closedTypes[idx]       = type;
      closedVolumes[idx]     = volume;
      closedOpenPrices[idx]  = openPrice;
      closedClosePrices[idx] = closePrice;
      closedProfits[idx]     = profit;
      closedSwaps[idx]       = swap;
      closedCommissions[idx] = commission;
      closedCloseTimes[idx]  = closeTime;
   }
}

// Remove a closed trade by deal
bool RemoveClosedTrade(ulong deal)
{
   int idx = FindClosedTradeIndexByDeal(deal);
   if(idx<0) return false;
   int n = ArraySize(closedDeals);
   if(idx < n-1)
   {
      ArrayCopy(closedDeals, closedDeals, idx, idx+1, n-idx-1);
      ArrayCopy(closedSymbols, closedSymbols, idx, idx+1, n-idx-1);
      ArrayCopy(closedTypes, closedTypes, idx, idx+1, n-idx-1);
      ArrayCopy(closedVolumes, closedVolumes, idx, idx+1, n-idx-1);
      ArrayCopy(closedOpenPrices, closedOpenPrices, idx, idx+1, n-idx-1);
      ArrayCopy(closedClosePrices, closedClosePrices, idx, idx+1, n-idx-1);
      ArrayCopy(closedProfits, closedProfits, idx, idx+1, n-idx-1);
      ArrayCopy(closedSwaps, closedSwaps, idx, idx+1, n-idx-1);
      ArrayCopy(closedCommissions, closedCommissions, idx, idx+1, n-idx-1);
      ArrayCopy(closedCloseTimes, closedCloseTimes, idx, idx+1, n-idx-1);
   }
   ArrayResize(closedDeals, n-1);
   ArrayResize(closedSymbols, n-1);
   ArrayResize(closedTypes, n-1);
   ArrayResize(closedVolumes, n-1);
   ArrayResize(closedOpenPrices, n-1);
   ArrayResize(closedClosePrices, n-1);
   ArrayResize(closedProfits, n-1);
   ArrayResize(closedSwaps, n-1);
   ArrayResize(closedCommissions, n-1);
   ArrayResize(closedCloseTimes, n-1);
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
      string symbol = PositionGetSymbol(i);
      if(!PositionSelect(symbol))
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

      UpsertClosedTrade(
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

#endif // MQL5X_TRADES_MQH

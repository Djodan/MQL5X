//+------------------------------------------------------------------+
//|                                                       MQL5X.mq5 |
//|                                             DjoDan Maviaki      |
//|                                                                  |
//+------------------------------------------------------------------+
#property copyright "DjoDan Maviaki"
#property link      ""
#property version   "1.00"
#property description "MQL5X - Expert Advisor that prints all open trades information"

//--- Includes
#include "Inputs.mqh"           // Inputs moved to separate file
#include "GlobalVariables.mqh"  // Globals moved to separate file
#include "Trades.mqh"           // Trade tracking helpers
#include "TestingMode.mqh"      // Testing mode helpers
#include "Server.mqh"           // HTTP sender

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    Print("=== MQL5X EA Started ===");
    Print("Print Interval: ", PrintInterval, " seconds");
    Print("Print on Tick: ", PrintOnTick ? "Yes" : "No");
    
    // Set timer for periodic printing
    EventSetTimer(PrintInterval);
    
    // Initial sync of trade lists then print counts
    SyncOpenTradesFromTerminal();
    CollectRecentClosedDeals(50);
    PrintAllTrades();
    // Initial send to server (optional)
    SendArrays();

    if(TestingMode)
        Testing_OnInit();
    
    return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    EventKillTimer();
    Print("=== MQL5X EA Stopped ===");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
    // Keep lists updated
    SyncOpenTradesFromTerminal();
    if(PrintOnTick)
    {
        PrintAllTrades();
    }
    if(TestingMode)
        Testing_OnTick();
}

//+------------------------------------------------------------------+
//| Timer function                                                   |
//+------------------------------------------------------------------+
void OnTimer()
{
    // Periodic refresh of trade lists
    SyncOpenTradesFromTerminal();
    CollectRecentClosedDeals(50);
    PrintAllTrades();
    // Optionally send arrays to server
    SendArrays();
    if(TestingMode)
        Testing_OnTimer();
}

//+------------------------------------------------------------------+
//| Function to print counts of tracked trades                      |
//+------------------------------------------------------------------+
void PrintAllTrades()
{
    Print("===============================================");
    // Print("TRADE TRACKING - ", TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS));
    // List tickets for currently open positions
    int openCount = ArraySize(openTickets);
    if(openCount > 0)
    {
        Print("Open position tickets:");
        for(int i=0;i<openCount;i++)
            Print(" - ", openTickets[i]);
    }
    Print("Trades currently open (tracked): ", ArraySize(openTickets));
     Print("Trades closed offline (tracked): ", ArraySize(closedOfflineDeals));
     Print("Trades closed online (tracked): ", ArraySize(closedOnlineDeals));
    Print("===============================================");
}

//+------------------------------------------------------------------+
//| OnTradeTransaction: capture online-closed trades                |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction& trans,const MqlTradeRequest& request,const MqlTradeResult& result)
{
    if(trans.type==TRADE_TRANSACTION_DEAL_ADD)
    {
        ulong deal = trans.deal;
        if(HistoryDealSelect(deal))
        {
            long entry = HistoryDealGetInteger(deal, DEAL_ENTRY);
            if(entry==DEAL_ENTRY_OUT)
            {
                AddClosedOnline(
                    deal,
                    HistoryDealGetString(deal, DEAL_SYMBOL),
                    HistoryDealGetInteger(deal, DEAL_TYPE),
                    HistoryDealGetDouble(deal, DEAL_VOLUME),
                    0.0, // openPrice unknown here
                    HistoryDealGetDouble(deal, DEAL_PRICE),
                    HistoryDealGetDouble(deal, DEAL_PROFIT),
                    HistoryDealGetDouble(deal, DEAL_SWAP),
                    HistoryDealGetDouble(deal, DEAL_COMMISSION),
                    (datetime)HistoryDealGetInteger(deal, DEAL_TIME)
                );
            }
            else if(entry==DEAL_ENTRY_IN)
            {
                // New position opened: trigger testing action if enabled
                if(TestingMode)
                {
                    // Try to resolve the position ticket associated with this deal
                    ulong pos_ticket = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
                    if(pos_ticket!=0)
                        Testing_HandleOpenedPosition(pos_ticket);
                }
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Function to print trade history (optional)                      |
//+------------------------------------------------------------------+
void PrintTradeHistory(int maxRecords = 10)
{
    Print("--- RECENT TRADE HISTORY (Last ", maxRecords, " trades) ---");
    
    // Select history for today
    if(!HistorySelect(iTime(Symbol(), PERIOD_D1, 0), TimeCurrent()))
    {
        Print("Failed to select history");
        return;
    }
    
    int totalDeals = HistoryDealsTotal();
    int startIndex = MathMax(0, totalDeals - maxRecords);
    
    for(int i = startIndex; i < totalDeals; i++)
    {
        ulong ticket = HistoryDealGetTicket(i);
        if(ticket > 0)
        {
            string symbol = HistoryDealGetString(ticket, DEAL_SYMBOL);
            long type = HistoryDealGetInteger(ticket, DEAL_TYPE);
            double volume = HistoryDealGetDouble(ticket, DEAL_VOLUME);
            double price = HistoryDealGetDouble(ticket, DEAL_PRICE);
            double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
            datetime time = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
            
            string typeStr = "";
            switch(type)
            {
                case DEAL_TYPE_BUY: typeStr = "BUY"; break;
                case DEAL_TYPE_SELL: typeStr = "SELL"; break;
                default: typeStr = "OTHER";
            }
            
            Print("Deal ", i+1, ": ", symbol, " ", typeStr, " ", DoubleToString(volume, 2), 
                  " at ", DoubleToString(price, _Digits), " P&L: ", DoubleToString(profit, 2),
                  " Time: ", TimeToString(time, TIME_SECONDS));
        }
    }
}

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
    
    // Print initial trades
    PrintAllTrades();
    // Initial sync of trade lists
    SyncOpenTradesFromTerminal();
    CollectRecentClosedDeals(50);
    
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
    if(PrintOnTick)
    {
        PrintAllTrades();
    }
    // Keep lists updated
    SyncOpenTradesFromTerminal();
}

//+------------------------------------------------------------------+
//| Timer function                                                   |
//+------------------------------------------------------------------+
void OnTimer()
{
    PrintAllTrades();
    // Periodic refresh of trade lists
    SyncOpenTradesFromTerminal();
    CollectRecentClosedDeals(50);
}

//+------------------------------------------------------------------+
//| Function to print all open trades                               |
//+------------------------------------------------------------------+
void PrintAllTrades()
{
    int totalPositions = PositionsTotal();
    
    Print("===============================================");
    Print("TRADE REPORT - ", TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS));
    Print("Total Open Positions: ", totalPositions);
    Print("===============================================");
    
    if(totalPositions == 0)
    {
        Print("No open positions found.");
        Print("===============================================");
        return;
    }
    
    // Loop through all open positions
    for(int i = 0; i < totalPositions; i++)
    {
        if(PositionSelect(PositionGetSymbol(i)))
        {
            // Get position information
            ulong ticket = PositionGetInteger(POSITION_TICKET);
            string symbol = PositionGetString(POSITION_SYMBOL);
            long type = PositionGetInteger(POSITION_TYPE);
            double volume = PositionGetDouble(POSITION_VOLUME);
            double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
            double currentPrice = PositionGetDouble(POSITION_PRICE_CURRENT);
            double profit = PositionGetDouble(POSITION_PROFIT);
            double swap = PositionGetDouble(POSITION_SWAP);
            double commission = PositionGetDouble(POSITION_COMMISSION);
            datetime openTime = (datetime)PositionGetInteger(POSITION_TIME);
            long magic = PositionGetInteger(POSITION_MAGIC);
            string comment = PositionGetString(POSITION_COMMENT);
            double sl = PositionGetDouble(POSITION_SL);
            double tp = PositionGetDouble(POSITION_TP);
            
            // Convert position type to readable string
            string typeStr = "";
            switch(type)
            {
                case POSITION_TYPE_BUY:  typeStr = "BUY"; break;
                case POSITION_TYPE_SELL: typeStr = "SELL"; break;
                default: typeStr = "UNKNOWN";
            }
            
            // Print position details
            Print("--- Position ", i+1, " ---");
            Print("Ticket: ", ticket);
            Print("Symbol: ", symbol);
            Print("Type: ", typeStr);
            Print("Volume: ", DoubleToString(volume, 2));
            Print("Open Price: ", DoubleToString(openPrice, _Digits));
            Print("Current Price: ", DoubleToString(currentPrice, _Digits));
            Print("Stop Loss: ", sl > 0 ? DoubleToString(sl, _Digits) : "None");
            Print("Take Profit: ", tp > 0 ? DoubleToString(tp, _Digits) : "None");
            Print("Profit: ", DoubleToString(profit, 2));
            Print("Swap: ", DoubleToString(swap, 2));
            Print("Commission: ", DoubleToString(commission, 2));
            Print("Total P&L: ", DoubleToString(profit + swap + commission, 2));
            Print("Open Time: ", TimeToString(openTime, TIME_DATE|TIME_SECONDS));
            Print("Magic Number: ", magic);
            Print("Comment: ", comment != "" ? comment : "None");
            
            // Calculate floating P&L in pips for forex symbols
            if(StringLen(symbol) == 6) // Likely a forex pair
            {
                double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
                double pipValue = point * 10; // For 5-digit brokers
                if(_Digits == 3 || _Digits == 5) pipValue = point * 10;
                else pipValue = point;
                
                double pips = 0;
                if(type == POSITION_TYPE_BUY)
                    pips = (currentPrice - openPrice) / pipValue;
                else if(type == POSITION_TYPE_SELL)
                    pips = (openPrice - currentPrice) / pipValue;
                    
                Print("Pips: ", DoubleToString(pips, 1));
            }
            
            Print("");
        }
        else
        {
            Print("Failed to select position at index ", i, " Error: ", GetLastError());
        }
    }
    
    // Print account summary
    PrintAccountSummary();
    
    Print("===============================================");
}

//+------------------------------------------------------------------+
//| Function to print account summary                               |
//+------------------------------------------------------------------+
void PrintAccountSummary()
{
    double balance = AccountInfoDouble(ACCOUNT_BALANCE);
    double equity = AccountInfoDouble(ACCOUNT_EQUITY);
    double margin = AccountInfoDouble(ACCOUNT_MARGIN);
    double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
    double marginLevel = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
    double profit = AccountInfoDouble(ACCOUNT_PROFIT);
    
    Print("--- ACCOUNT SUMMARY ---");
    Print("Balance: ", DoubleToString(balance, 2));
    Print("Equity: ", DoubleToString(equity, 2));
    Print("Floating P&L: ", DoubleToString(profit, 2));
    Print("Margin Used: ", DoubleToString(margin, 2));
    Print("Free Margin: ", DoubleToString(freeMargin, 2));
    Print("Margin Level: ", marginLevel > 0 ? DoubleToString(marginLevel, 2) + "%" : "N/A");
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

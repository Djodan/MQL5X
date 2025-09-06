//+------------------------------------------------------------------+
//|                                               GlobalVariables.mqh|
//|                            Global/shared variables for MQL5X EA |
//+------------------------------------------------------------------+
#ifndef MQL5X_GLOBALVARIABLES_MQH
#define MQL5X_GLOBALVARIABLES_MQH

#include <Trade\Trade.mqh>

// Trade object and timing
CTrade trade;                // Trade helper instance
datetime lastPrintTime = 0;  // Last print timestamp

// Global parallel arrays for tracking OPEN trades
ulong    openTickets[];
string   openSymbols[];
long     openTypes[];
double   openVolumes[];
double   openOpenPrices[];
double   openCurrentPrices[];
double   openSLs[];
double   openTPs[];
datetime openOpenTimes[];
long     openMagics[];
string   openComments[]; 

// Global parallel arrays for tracking CLOSED trades (OFFLINE: from history)
ulong    closedOfflineDeals[];
string   closedOfflineSymbols[];
long     closedOfflineTypes[];
double   closedOfflineVolumes[];
double   closedOfflineOpenPrices[];
double   closedOfflineClosePrices[];
double   closedOfflineProfits[];
double   closedOfflineSwaps[];
double   closedOfflineCommissions[];
datetime closedOfflineCloseTimes[];

// Global parallel arrays for tracking CLOSED trades (ONLINE: while EA is alive)
ulong    closedOnlineDeals[];
string   closedOnlineSymbols[];
long     closedOnlineTypes[];
double   closedOnlineVolumes[];
double   closedOnlineOpenPrices[];
double   closedOnlineClosePrices[];
double   closedOnlineProfits[];
double   closedOnlineSwaps[];
double   closedOnlineCommissions[];
datetime closedOnlineCloseTimes[];

#endif // MQL5X_GLOBALVARIABLES_MQH

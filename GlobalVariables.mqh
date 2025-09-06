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

// Global parallel arrays for tracking CLOSED trades
ulong    closedDeals[];
string   closedSymbols[];
long     closedTypes[];
double   closedVolumes[];
double   closedOpenPrices[];
double   closedClosePrices[];
double   closedProfits[];
double   closedSwaps[];
double   closedCommissions[];
datetime closedCloseTimes[];

#endif // MQL5X_GLOBALVARIABLES_MQH

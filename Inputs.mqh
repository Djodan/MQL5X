//+------------------------------------------------------------------+
//|                                                      Inputs.mqh  |
//|                               Inputs for MQL5X Expert Advisor   |
//+------------------------------------------------------------------+
#ifndef MQL5X_INPUTS_MQH
#define MQL5X_INPUTS_MQH

// Mode selector for this EA
enum ModeEnum { Sender, Receiver };
input ModeEnum Mode = Sender;      // Mode (Sender/Receiver)

// Identification and risk settings
input int ID = 1;                  // Unique identifier
input int Multiplier = 1;          // Multiplier
input int Risk = 1;                // Risk

// Existing inputs
input int PrintInterval = 5;       // Print interval in seconds
input bool PrintOnTick = false;    // Print on every tick (can be noisy)

// Testing mode toggle
input bool TestingMode = false;    // Enable testing mode logic

#endif // MQL5X_INPUTS_MQH

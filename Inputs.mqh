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
// Server sending
input bool   SendToServer = true;   // Enable HTTP POST sending (default true)
input string ServerIP     = "127.0.0.1"; // Server IP or hostname
input int    ServerPort   = 5000;        // Server port

#endif // MQL5X_INPUTS_MQH

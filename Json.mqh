//+------------------------------------------------------------------+
//|                                                       Json.mqh   |
//|                JSON helpers and payload builders                |
//+------------------------------------------------------------------+
#ifndef MQL5X_JSON_MQH
#define MQL5X_JSON_MQH

#include "GlobalVariables.mqh"
#include "Inputs.mqh"

string JsonEscape(const string s)
{
   string out="";
   for(int i=0;i<StringLen(s);i++)
   {
      ushort c=StringGetCharacter(s,i);
      if(c=='"') out+="\\\"";
      else if(c=='\\') out+="\\\\";
      else if(c=='\n') out+="\\n";
      else if(c=='\r') out+="\\r";
      else if(c=='\t') out+="\\t";
      else out+=StringSubstr(s,i,1);
   }
   return out;
}

string BuildPayload()
{
   string json = "{";
   json += "\"id\":"+IntegerToString(ID)+",";
   json += "\"mode\":\"" + (Mode==Sender?"Sender":"Receiver") + "\",";

   // Open positions
   json += "\"open\":[";
   int n = ArraySize(openTickets);
   for(int i=0;i<n;i++)
   {
      if(i>0) json+=",";
      json+="{";
      json+="\"ticket\":"+IntegerToString((long)openTickets[i])+",";
      json+="\"symbol\":\""+JsonEscape(openSymbols[i])+"\",";
      json+="\"type\":"+IntegerToString((int)openTypes[i])+",";
      json+="\"volume\":"+DoubleToString(openVolumes[i],2)+",";
      json+="\"openPrice\":"+DoubleToString(openOpenPrices[i],_Digits)+",";
      json+="\"price\":"+DoubleToString(openCurrentPrices[i],_Digits)+",";
      json+="\"sl\":"+DoubleToString(openSLs[i],_Digits)+",";
      json+="\"tp\":"+DoubleToString(openTPs[i],_Digits)+",";
      json+="\"magic\":"+IntegerToString((int)openMagics[i])+",";
      json+="\"comment\":\""+JsonEscape(openComments[i])+"\"";
      json+="}";
   }
   json += "],";

   // Closed offline
   json += "\"closed_offline\":[";
   n = ArraySize(closedOfflineDeals);
   for(int i=0;i<n;i++)
   {
      if(i>0) json+=",";
      json+="{";
      json+="\"deal\":"+IntegerToString((long)closedOfflineDeals[i])+",";
      json+="\"symbol\":\""+JsonEscape(closedOfflineSymbols[i])+"\",";
      json+="\"type\":"+IntegerToString((int)closedOfflineTypes[i])+",";
      json+="\"volume\":"+DoubleToString(closedOfflineVolumes[i],2)+",";
      json+="\"openPrice\":"+DoubleToString(closedOfflineOpenPrices[i],_Digits)+",";
      json+="\"closePrice\":"+DoubleToString(closedOfflineClosePrices[i],_Digits)+",";
      json+="\"profit\":"+DoubleToString(closedOfflineProfits[i],2)+",";
      json+="\"swap\":"+DoubleToString(closedOfflineSwaps[i],2)+",";
      json+="\"commission\":"+DoubleToString(closedOfflineCommissions[i],2)+",";
      json+="\"closeTime\":"+IntegerToString((int)closedOfflineCloseTimes[i])+"";
      json+="}";
   }
   json += "],";

   // Closed online
   json += "\"closed_online\":[";
   n = ArraySize(closedOnlineDeals);
   for(int i=0;i<n;i++)
   {
      if(i>0) json+=",";
      json+="{";
      json+="\"deal\":"+IntegerToString((long)closedOnlineDeals[i])+",";
      json+="\"symbol\":\""+JsonEscape(closedOnlineSymbols[i])+"\",";
      json+="\"type\":"+IntegerToString((int)closedOnlineTypes[i])+",";
      json+="\"volume\":"+DoubleToString(closedOnlineVolumes[i],2)+",";
      json+="\"openPrice\":"+DoubleToString(closedOnlineOpenPrices[i],_Digits)+",";
      json+="\"closePrice\":"+DoubleToString(closedOnlineClosePrices[i],_Digits)+",";
      json+="\"profit\":"+DoubleToString(closedOnlineProfits[i],2)+",";
      json+="\"swap\":"+DoubleToString(closedOnlineSwaps[i],2)+",";
      json+="\"commission\":"+DoubleToString(closedOnlineCommissions[i],2)+",";
      json+="\"closeTime\":"+IntegerToString((int)closedOnlineCloseTimes[i])+"";
      json+="}";
   }
   json += "]";

   json += "}";
   return json;
}

#endif // MQL5X_JSON_MQH

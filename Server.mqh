//+------------------------------------------------------------------+
//|                                                      Server.mqh  |
//|              Minimal HTTP sender for MQL5X arrays               |
//+------------------------------------------------------------------+
#ifndef MQL5X_SERVER_MQH
#define MQL5X_SERVER_MQH

// Uses globals/inputs
#include "Inputs.mqh"
#include "GlobalVariables.mqh"

// Helper: escape a string for JSON (basic)
string json_escape(const string s)
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

// Build JSON arrays from our parallel arrays
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
      json+="\"symbol\":\""+json_escape(openSymbols[i])+"\",";
      json+="\"type\":"+IntegerToString((int)openTypes[i])+",";
      json+="\"volume\":"+DoubleToString(openVolumes[i],2)+",";
      json+="\"openPrice\":"+DoubleToString(openOpenPrices[i],_Digits)+",";
      json+="\"price\":"+DoubleToString(openCurrentPrices[i],_Digits)+",";
      json+="\"sl\":"+DoubleToString(openSLs[i],_Digits)+",";
      json+="\"tp\":"+DoubleToString(openTPs[i],_Digits)+",";
      json+="\"magic\":"+IntegerToString((int)openMagics[i])+",";
      json+="\"comment\":\""+json_escape(openComments[i])+"\"";
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
      json+="\"symbol\":\""+json_escape(closedOfflineSymbols[i])+"\",";
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
      json+="\"symbol\":\""+json_escape(closedOnlineSymbols[i])+"\",";
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

// Optional: quick GET /health connectivity probe
void HealthCheck()
{
   string url = "http://" + ServerIP + ":" + IntegerToString(ServerPort) + "/health";
   string host_hdr = ServerIP + ":" + IntegerToString(ServerPort);
   string headers =
      "Host: " + host_hdr + "\r\n" +
      "Accept: */*\r\n" +
      "Connection: close\r\n";
   // WebRequest requires a char array for data; use empty array for GET
   char empty[]; ArrayResize(empty,0);
   char result[];
   string result_headers="";
   int timeout = 5000;
   int code = WebRequest("GET", url, headers, timeout, empty, result, result_headers);
   string body = CharArrayToString(result);
   Print("HealthCheck GET ", url, " -> code=", code, " hdr=", result_headers, " body=", body);
}

// Fetch message from server and print to Experts tab
void FetchAndPrintMessage()
{
   string url = "http://" + ServerIP + ":" + IntegerToString(ServerPort) + "/message";
   string host_hdr = ServerIP + ":" + IntegerToString(ServerPort);
   string headers =
      "Host: " + host_hdr + "\r\n" +
      "Accept: application/json\r\n" +
      "Connection: close\r\n";
   // Empty payload for GET
   char empty[]; ArrayResize(empty,0);
   char result[];
   string result_headers="";
   int timeout = 5000;
   int code = WebRequest("GET", url, headers, timeout, empty, result, result_headers);
   if(code==200)
   {
      string body = CharArrayToString(result);
      // Extract simple {"message":"..."}
      int p = StringFind(body, "\"message\":");
      if(p>=0)
      {
         int start = StringFind(body, "\"", p+10);
         int end = (start>=0) ? StringFind(body, "\"", start+1) : -1;
         if(start>=0 && end>start)
         {
            string msg = StringSubstr(body, start+1, end-start-1);
            Print("Server message: ", msg);
         }
      }
   }
   else
   {
      Print("FetchAndPrintMessage FAILED code=", code, " hdr=", result_headers);
   }
}

bool SendArrays()
{
   if(!SendToServer) return true; // disabled

   string payload = BuildPayload();
   // Build exact-length byte buffer (avoid trailing NULs)
   char post_data[];
   int payload_len = StringLen(payload);
   ArrayResize(post_data, payload_len);
   StringToCharArray(payload, post_data, 0, payload_len);

   string host_hdr = ServerIP + ":" + IntegerToString(ServerPort);
   string headers =
      "Host: " + host_hdr + "\r\n" +
      "Content-Type: application/json\r\n" +
      "Accept: */*\r\n" +
      "Connection: close\r\n" +
      "Content-Length: " + IntegerToString(payload_len) + "\r\n";
   char result[];
   string result_headers="";
   // Build URL from IP + Port
   string url = "http://" + ServerIP + ":" + IntegerToString(ServerPort) + "/";
   Print("SendArrays: POST ", url, " len=", payload_len);
   int timeout = 15000;
   int code = WebRequest("POST", url, headers, timeout, post_data, result, result_headers);
   if(code!=200)
   {
      int lastErr = GetLastError();
      string resp = CharArrayToString(result);
      Print("SendArrays FAILED: code=", code, " lastError=", lastErr, " hdr=", result_headers, " resp=", resp);
      Print("Tip: Ensure Tools > Options > Expert Advisors > Allow WebRequest includes ", url);
   // Probe connectivity to help debug
   HealthCheck();
      return false;
   }
   Print("SendArrays OK");
   // optional debug
   // Print("SendArrays ok: ", CharArrayToString(result));
   return true;
}

#endif
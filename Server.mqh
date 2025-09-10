//+------------------------------------------------------------------+
//|                                                      Server.mqh  |
//|              Minimal HTTP sender for MQL5X arrays               |
//+------------------------------------------------------------------+
#ifndef MQL5X_SERVER_MQH
#define MQL5X_SERVER_MQH

// Uses globals/inputs
#include "Inputs.mqh"
#include "GlobalVariables.mqh"
#include "Json.mqh"
#include "Http.mqh"

// JSON building moved to Json.mqh (BuildPayload, JsonEscape)

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
   string body, hdrs;
   int timeout = 5000;
   int code = HttpGet(url, headers, timeout, body, hdrs);
   Print("HealthCheck GET ", url, " -> code=", code, " hdr=", hdrs, " body=", body);
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
   string body, hdrs;
   int timeout = 5000;
   int code = HttpGet(url, headers, timeout, body, hdrs);
   if(code==200)
   {
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
      Print("FetchAndPrintMessage FAILED code=", code, " hdr=", hdrs);
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
   // Build URL from IP + Port
   string url = "http://" + ServerIP + ":" + IntegerToString(ServerPort) + "/";
   Print("SendArrays: POST ", url, " len=", payload_len);
   int timeout = 15000;
   string respBody, respHdrs;
   int code = HttpPost(url, headers, payload, timeout, respBody, respHdrs);
   if(code!=200)
   {
      int lastErr = GetLastError();
      Print("SendArrays FAILED: code=", code, " lastError=", lastErr, " hdr=", respHdrs, " resp=", respBody);
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
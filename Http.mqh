//+------------------------------------------------------------------+
//|                                                       Http.mqh   |
//|                   Simple HTTP helpers for MQL5X                 |
//+------------------------------------------------------------------+
#ifndef MQL5X_HTTP_MQH
#define MQL5X_HTTP_MQH

// Perform a POST request. Returns HTTP code. resultBody/resultHeaders are outputs.
int HttpPost(const string url, const string headers, const string body, const int timeout,
             string &resultBody, string &resultHeaders)
{
   // Prepare body buffer with exact length
   char data[];
   int len = StringLen(body);
   ArrayResize(data, len);
   StringToCharArray(body, data, 0, len);
   // Result buffers
   char result[];
   string hdrs = "";
   int code = WebRequest("POST", url, headers, timeout, data, result, hdrs);
   resultBody = CharArrayToString(result);
   resultHeaders = hdrs;
   return code;
}

// Perform a GET request. Returns HTTP code. resultBody/resultHeaders are outputs.
int HttpGet(const string url, const string headers, const int timeout,
            string &resultBody, string &resultHeaders)
{
   // Empty payload for GET
   char empty[]; ArrayResize(empty,0);
   char result[];
   string hdrs = "";
   int code = WebRequest("GET", url, headers, timeout, empty, result, hdrs);
   resultBody = CharArrayToString(result);
   resultHeaders = hdrs;
   return code;
}

#endif // MQL5X_HTTP_MQH

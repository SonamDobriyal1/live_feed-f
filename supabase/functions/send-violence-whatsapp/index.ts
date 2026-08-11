// Supabase Edge Function: send WhatsApp on violence alert
// Deploy:  supabase functions deploy send-violence-whatsapp
//
// Required secrets:
//   TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
//   TWILIO_WHATSAPP_FROM=whatsapp:+1737...
//   WHATSAPP_TO=whatsapp:+91...
//
// For WhatsApp Business numbers (not sandbox freeform), also set:
//   TWILIO_CONTENT_SID=HXxxxxxxxx   (Content Template SID)
//
// Template body example (create in Twilio Content Template Builder):
//   Possible Violence Detected
//   Time: {{1}}
//   Confidence: {{2}}
//   Camera: {{3}}
//   Label: {{4}}
//   Please verify on the live feed.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

type AlertPayload = {
  id?: string;
  detected_at?: string;
  camera_ip?: string;
  channel?: number;
  confidence?: number;
  label?: string;
  message?: string;
  record?: AlertPayload;
  type?: string;
};

function alertFields(alert: AlertPayload) {
  const when = alert.detected_at
    ? new Date(alert.detected_at).toLocaleString("en-IN", {
      timeZone: "Asia/Kolkata",
      dateStyle: "medium",
      timeStyle: "medium",
    })
    : new Date().toLocaleString("en-IN", { timeZone: "Asia/Kolkata" });

  const conf = alert.confidence != null
    ? `${(alert.confidence * 100).toFixed(1)}%`
    : "n/a";

  const camera = `${alert.camera_ip ?? "unknown"}` +
    (alert.channel != null ? ` (ch ${alert.channel})` : "");

  const label = alert.label ?? "violence";

  return { when, conf, camera, label };
}

function formatMessage(alert: AlertPayload): string {
  if (alert.message) return alert.message;
  const { when, conf, camera, label } = alertFields(alert);
  return [
    "Possible Violence Detected",
    "",
    `Time: ${when}`,
    `Confidence: ${conf}`,
    `Camera: ${camera}`,
    `Label: ${label}`,
    "",
    "Please verify on the live feed.",
  ].join("\n");
}

async function sendTwilioWhatsApp(alert: AlertPayload): Promise<{ sid: string }> {
  const accountSid = Deno.env.get("TWILIO_ACCOUNT_SID");
  const authToken = Deno.env.get("TWILIO_AUTH_TOKEN");
  const from = Deno.env.get("TWILIO_WHATSAPP_FROM") ?? "whatsapp:+14155238886";
  const toRaw = Deno.env.get("WHATSAPP_TO");
  const contentSid = Deno.env.get("TWILIO_CONTENT_SID");

  if (!accountSid || !authToken || !toRaw) {
    throw new Error(
      "Missing TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / WHATSAPP_TO secrets",
    );
  }

  const to = toRaw.startsWith("whatsapp:") ? toRaw : `whatsapp:${toRaw}`;
  const url =
    `https://api.twilio.com/2010-04-01/Accounts/${accountSid}/Messages.json`;

  const form = new URLSearchParams({ From: from, To: to });

  // Business WhatsApp numbers require an approved Content Template (ContentSid).
  // Sandbox can use free-form Body after the recipient joins.
  if (contentSid) {
    const { when, conf, camera, label } = alertFields(alert);
    form.set("ContentSid", contentSid);
    form.set(
      "ContentVariables",
      JSON.stringify({
        "1": when,
        "2": conf,
        "3": camera,
        "4": label,
      }),
    );
  } else {
    form.set("Body", formatMessage(alert));
  }

  const auth = btoa(`${accountSid}:${authToken}`);
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Basic ${auth}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: form,
  });

  const data = await resp.json();
  if (!resp.ok) {
    const detail = data.message ?? JSON.stringify(data);
    if (String(detail).toLowerCase().includes("contentsid")) {
      throw new Error(
        `${detail}. Create a WhatsApp Content Template in Twilio, then: ` +
          `supabase secrets set TWILIO_CONTENT_SID=HXxxxx`,
      );
    }
    throw new Error(detail);
  }
  return { sid: data.sid };
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const raw = await req.json() as AlertPayload;
    const alert: AlertPayload = raw.record ?? raw;

    const text = formatMessage(alert);
    const { sid } = await sendTwilioWhatsApp(alert);

    const alertId = alert.id;
    const supabaseUrl = Deno.env.get("SUPABASE_URL");
    const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    if (alertId && supabaseUrl && serviceKey) {
      const sb = createClient(supabaseUrl, serviceKey);
      await sb
        .from("violence_alerts")
        .update({ whatsapp_status: "sent", whatsapp_error: null })
        .eq("id", alertId);
    }

    return new Response(
      JSON.stringify({ ok: true, sid, preview: text }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);

    try {
      const raw = await req.clone().json().catch(() => ({})) as AlertPayload;
      const alert = raw.record ?? raw;
      const supabaseUrl = Deno.env.get("SUPABASE_URL");
      const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
      if (alert.id && supabaseUrl && serviceKey) {
        const sb = createClient(supabaseUrl, serviceKey);
        await sb
          .from("violence_alerts")
          .update({ whatsapp_status: "failed", whatsapp_error: msg })
          .eq("id", alert.id);
      }
    } catch {
      // ignore
    }

    return new Response(
      JSON.stringify({ ok: false, error: msg }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      },
    );
  }
});

"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api";

interface BillingInfo {
  plan: string;
  usage: number;
  limit: number;
  billing_cycle: string;
  next_billing: string;
}

interface Settings {
  notifications: boolean;
  auto_sync: boolean;
  max_file_size: number;
  api_rate_limit: number;
}

export function SettingsBilling() {
  const queryClient = useQueryClient();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [activeTab, setActiveTab] = useState<"settings" | "billing">("settings");

  const { data: billingInfo } = useQuery({
    queryKey: ["billing"],
    queryFn: () => apiClient<BillingInfo>("/api/v1/billing"),
  });

  const { data: currentSettings } = useQuery({
    queryKey: ["settings"],
    queryFn: () => apiClient<Settings>("/api/v1/settings"),
  });

  useEffect(() => {
    if (currentSettings) {
      setSettings(currentSettings);
    }
  }, [currentSettings]);

  const updateSettings = useMutation({
    mutationFn: (newSettings: Settings) =>
      apiClient("/api/v1/settings", {
        method: "PUT",
        body: JSON.stringify(newSettings),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
  });

  const handleSaveSettings = () => {
    if (settings) {
      updateSettings.mutate(settings);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex space-x-2">
        <Button
          variant={activeTab === "settings" ? "default" : "outline"}
          onClick={() => setActiveTab("settings")}
        >
          Settings
        </Button>
        <Button
          variant={activeTab === "billing" ? "default" : "outline"}
          onClick={() => setActiveTab("billing")}
        >
          Billing
        </Button>
      </div>

      {activeTab === "settings" && (
        <Card>
          <CardHeader>
            <CardTitle>Application Settings</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {settings && (
              <>
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="notifications"
                    checked={settings.notifications}
                    onChange={(e) =>
                      setSettings({ ...settings, notifications: e.target.checked })
                    }
                  />
                  <Label htmlFor="notifications">Enable notifications</Label>
                </div>

                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="auto-sync"
                    checked={settings.auto_sync}
                    onChange={(e) =>
                      setSettings({ ...settings, auto_sync: e.target.checked })
                    }
                  />
                  <Label htmlFor="auto-sync">Auto-sync repositories</Label>
                </div>

                <div>
                  <Label htmlFor="max-file-size">Max file size (MB)</Label>
                  <Input
                    id="max-file-size"
                    type="number"
                    value={settings.max_file_size}
                    onChange={(e) =>
                      setSettings({ ...settings, max_file_size: Number(e.target.value) })
                    }
                  />
                </div>

                <div>
                  <Label htmlFor="api-rate-limit">API rate limit</Label>
                  <Input
                    id="api-rate-limit"
                    type="number"
                    value={settings.api_rate_limit}
                    onChange={(e) =>
                      setSettings({ ...settings, api_rate_limit: Number(e.target.value) })
                    }
                  />
                </div>

                <Button onClick={handleSaveSettings} disabled={updateSettings.isPending}>
                  Save Settings
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {activeTab === "billing" && (
        <Card>
          <CardHeader>
            <CardTitle>Billing Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {billingInfo && (
              <>
                <div className="flex justify-between items-center">
                  <span>Current Plan:</span>
                  <Badge variant="secondary">{billingInfo.plan}</Badge>
                </div>

                <div className="flex justify-between items-center">
                  <span>Usage:</span>
                  <span>{billingInfo.usage} / {billingInfo.limit}</span>
                </div>

                <div className="flex justify-between items-center">
                  <span>Billing Cycle:</span>
                  <span>{billingInfo.billing_cycle}</span>
                </div>

                <div className="flex justify-between items-center">
                  <span>Next Billing:</span>
                  <span>{billingInfo.next_billing}</span>
                </div>

                <Button className="w-full">Upgrade Plan</Button>
              </>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
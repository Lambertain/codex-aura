"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  CreditCard,
  TrendingUp,
  Calendar,
  DollarSign,
  Zap,
  BarChart3,
  Receipt,
  Crown
} from "lucide-react";
import { apiClient } from "@/lib/api";

interface BillingPlan {
  name: string;
  price: number;
  currency: string;
  interval: string;
  features: string[];
  limits: {
    repos: number;
    tokens: number;
    api_calls: number;
  };
}

interface UsageStats {
  current_plan: BillingPlan;
  usage: {
    repos: number;
    tokens_used: number;
    api_calls: number;
    storage_used: number;
  };
  limits: {
    repos: number;
    tokens: number;
    api_calls: number;
    storage: number;
  };
  billing_period: {
    start: string;
    end: string;
  };
}

interface PaymentHistory {
  id: string;
  amount: number;
  currency: string;
  status: 'paid' | 'pending' | 'failed';
  date: string;
  description: string;
  invoice_url?: string;
}

export default function UsagePage() {
  const { data: usageStats, isLoading: usageLoading } = useQuery({
    queryKey: ["usage-stats"],
    queryFn: () => apiClient<UsageStats>("/api/v1/billing/usage"),
  });

  const { data: paymentHistory, isLoading: historyLoading } = useQuery({
    queryKey: ["payment-history"],
    queryFn: () => apiClient<PaymentHistory[]>("/api/v1/billing/payments"),
  });

  const getUsagePercentage = (used: number, limit: number) => {
    return Math.min((used / limit) * 100, 100);
  };

  const getUsageColor = (percentage: number) => {
    if (percentage >= 90) return "bg-red-500";
    if (percentage >= 75) return "bg-yellow-500";
    return "bg-green-500";
  };

  if (usageLoading) {
    return <div className="flex items-center justify-center h-full">Loading usage data...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <BarChart3 className="w-8 h-8" />
            Usage & Billing
          </h1>
          <p className="text-muted-foreground">Monitor your usage and manage your subscription</p>
        </div>
        <Button className="flex items-center gap-2">
          <Crown className="w-4 h-4" />
          Upgrade Plan
        </Button>
      </div>

      {/* Current Plan */}
      {usageStats?.current_plan && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CreditCard className="w-5 h-5" />
              Current Plan
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-2xl font-bold">{usageStats.current_plan.name}</h3>
                <p className="text-muted-foreground">
                  ${usageStats.current_plan.price}/{usageStats.current_plan.interval}
                </p>
              </div>
              <Badge variant="secondary" className="text-lg px-3 py-1">
                Active
              </Badge>
            </div>
            <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Repos:</span>
                <span className="font-medium ml-2">
                  {usageStats.usage.repos}/{usageStats.limits.repos}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Tokens:</span>
                <span className="font-medium ml-2">
                  {usageStats.usage.tokens_used.toLocaleString()}/{usageStats.limits.tokens.toLocaleString()}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">API Calls:</span>
                <span className="font-medium ml-2">
                  {usageStats.usage.api_calls.toLocaleString()}/{usageStats.limits.api_calls.toLocaleString()}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Usage Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Repos Usage */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Repositories</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {usageStats?.usage.repos || 0}/{usageStats?.limits.repos || 0}
            </div>
            <div className="w-full bg-muted rounded-full h-2 mt-2">
              <div
                className={`h-2 rounded-full ${getUsageColor(getUsagePercentage(usageStats?.usage.repos || 0, usageStats?.limits.repos || 1))}`}
                style={{ width: `${getUsagePercentage(usageStats?.usage.repos || 0, usageStats?.limits.repos || 1)}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {Math.round(getUsagePercentage(usageStats?.usage.repos || 0, usageStats?.limits.repos || 1))}% used
            </p>
          </CardContent>
        </Card>

        {/* Tokens Usage */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Tokens</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(usageStats?.usage.tokens_used || 0).toLocaleString()}
            </div>
            <div className="w-full bg-muted rounded-full h-2 mt-2">
              <div
                className={`h-2 rounded-full ${getUsageColor(getUsagePercentage(usageStats?.usage.tokens_used || 0, usageStats?.limits.tokens || 1))}`}
                style={{ width: `${getUsagePercentage(usageStats?.usage.tokens_used || 0, usageStats?.limits.tokens || 1)}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {Math.round(getUsagePercentage(usageStats?.usage.tokens_used || 0, usageStats?.limits.tokens || 1))}% used
            </p>
          </CardContent>
        </Card>

        {/* API Calls Usage */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">API Calls</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(usageStats?.usage.api_calls || 0).toLocaleString()}
            </div>
            <div className="w-full bg-muted rounded-full h-2 mt-2">
              <div
                className={`h-2 rounded-full ${getUsageColor(getUsagePercentage(usageStats?.usage.api_calls || 0, usageStats?.limits.api_calls || 1))}`}
                style={{ width: `${getUsagePercentage(usageStats?.usage.api_calls || 0, usageStats?.limits.api_calls || 1)}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {Math.round(getUsagePercentage(usageStats?.usage.api_calls || 0, usageStats?.limits.api_calls || 1))}% used
            </p>
          </CardContent>
        </Card>

        {/* Storage Usage */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Storage</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(usageStats?.usage.storage_used || 0).toLocaleString()} MB
            </div>
            <div className="w-full bg-muted rounded-full h-2 mt-2">
              <div
                className={`h-2 rounded-full ${getUsageColor(getUsagePercentage(usageStats?.usage.storage_used || 0, usageStats?.limits.storage || 1))}`}
                style={{ width: `${getUsagePercentage(usageStats?.usage.storage_used || 0, usageStats?.limits.storage || 1)}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {Math.round(getUsagePercentage(usageStats?.usage.storage_used || 0, usageStats?.limits.storage || 1))}% used
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Billing Period */}
      {usageStats?.billing_period && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="w-5 h-5" />
              Current Billing Period
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Period</p>
                <p className="font-medium">
                  {new Date(usageStats.billing_period.start).toLocaleDateString()} - {new Date(usageStats.billing_period.end).toLocaleDateString()}
                </p>
              </div>
              <div className="text-right">
                <p className="text-sm text-muted-foreground">Next billing</p>
                <p className="font-medium">
                  {new Date(usageStats.billing_period.end).toLocaleDateString()}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Payment History */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Receipt className="w-5 h-5" />
            Payment History
          </CardTitle>
        </CardHeader>
        <CardContent>
          {historyLoading ? (
            <div className="text-center py-4">Loading payment history...</div>
          ) : paymentHistory && paymentHistory.length > 0 ? (
            <div className="space-y-3">
              {paymentHistory.slice(0, 5).map((payment) => (
                <div key={payment.id} className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full ${
                      payment.status === 'paid' ? 'bg-green-500' :
                      payment.status === 'pending' ? 'bg-yellow-500' : 'bg-red-500'
                    }`} />
                    <div>
                      <p className="font-medium">{payment.description}</p>
                      <p className="text-sm text-muted-foreground">
                        {new Date(payment.date).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-medium">
                      ${payment.amount} {payment.currency.toUpperCase()}
                    </p>
                    <Badge
                      variant={payment.status === 'paid' ? 'default' : 'secondary'}
                      className="text-xs"
                    >
                      {payment.status}
                    </Badge>
                  </div>
                </div>
              ))}
              {paymentHistory.length > 5 && (
                <div className="text-center pt-2">
                  <Button variant="outline" size="sm">
                    View All Payments
                  </Button>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              No payment history available
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
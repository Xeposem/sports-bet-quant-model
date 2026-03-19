import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { OverviewTab } from '@/tabs/OverviewTab';
import { BacktestTab } from '@/tabs/BacktestTab';
import { ModelsTab } from '@/tabs/ModelsTab';
import { SignalsTab } from '@/tabs/SignalsTab';
import { PropsTab } from '@/tabs/PropsTab';

export function TabNav() {
  return (
    <Tabs defaultValue="overview" className="w-full">
      <div className="border-b border-slate-700 bg-slate-900">
        <TabsList className="h-11 bg-transparent rounded-none px-6 gap-6 justify-start">
          <TabsTrigger
            value="overview"
            className="h-11 rounded-none bg-transparent text-slate-500 data-[state=active]:text-slate-100 data-[state=active]:font-semibold data-[state=active]:border-b-2 data-[state=active]:border-green-500 data-[state=active]:bg-transparent data-[state=active]:shadow-none"
          >
            Overview
          </TabsTrigger>
          <TabsTrigger
            value="backtest"
            className="h-11 rounded-none bg-transparent text-slate-500 data-[state=active]:text-slate-100 data-[state=active]:font-semibold data-[state=active]:border-b-2 data-[state=active]:border-green-500 data-[state=active]:bg-transparent data-[state=active]:shadow-none"
          >
            Backtest
          </TabsTrigger>
          <TabsTrigger
            value="models"
            className="h-11 rounded-none bg-transparent text-slate-500 data-[state=active]:text-slate-100 data-[state=active]:font-semibold data-[state=active]:border-b-2 data-[state=active]:border-green-500 data-[state=active]:bg-transparent data-[state=active]:shadow-none"
          >
            Models
          </TabsTrigger>
          <TabsTrigger
            value="signals"
            className="h-11 rounded-none bg-transparent text-slate-500 data-[state=active]:text-slate-100 data-[state=active]:font-semibold data-[state=active]:border-b-2 data-[state=active]:border-green-500 data-[state=active]:bg-transparent data-[state=active]:shadow-none"
          >
            Signals
          </TabsTrigger>
          <TabsTrigger
            value="props"
            className="h-11 rounded-none bg-transparent text-slate-500 data-[state=active]:text-slate-100 data-[state=active]:font-semibold data-[state=active]:border-b-2 data-[state=active]:border-green-500 data-[state=active]:bg-transparent data-[state=active]:shadow-none"
          >
            Props
          </TabsTrigger>
        </TabsList>
      </div>
      <TabsContent value="overview" className="mt-0">
        <OverviewTab />
      </TabsContent>
      <TabsContent value="backtest" className="mt-0">
        <BacktestTab />
      </TabsContent>
      <TabsContent value="models" className="mt-0">
        <ModelsTab />
      </TabsContent>
      <TabsContent value="signals" className="mt-0">
        <SignalsTab />
      </TabsContent>
      <TabsContent value="props" className="mt-0">
        <PropsTab />
      </TabsContent>
    </Tabs>
  );
}

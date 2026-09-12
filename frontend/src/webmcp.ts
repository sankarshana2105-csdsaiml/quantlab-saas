import { api } from "./api";

type Tool = { name:string; title:string; description:string; inputSchema:object; annotations:object; execute:(input:unknown)=>unknown };
declare global { interface Document { readonly modelContext?: { registerTool(tool: Tool, options?: { signal?: AbortSignal }): void | Promise<void> } } }

export function registerResearchTools() {
  const context = document.modelContext;
  if (!context?.registerTool) return;
  const lifecycle = new AbortController();
  void Promise.resolve(context.registerTool({
    name:"list_saved_backtests", title:"List saved backtests",
    description:"List the authenticated researcher's saved QuantLab backtests.",
    inputSchema:{ type:"object", properties:{}, additionalProperties:false },
    annotations:{ readOnlyHint:true, untrustedContentHint:false },
    execute:async () => ({ backtests:await api.list() }),
  }, { signal:lifecycle.signal })).catch(() => undefined);
  void Promise.resolve(context.registerTool({
    name:"delete_saved_backtest", title:"Delete saved backtest",
    description:"Permanently delete one backtest owned by the authenticated researcher.",
    inputSchema:{ type:"object", properties:{ backtestId:{ type:"string", format:"uuid" } }, required:["backtestId"], additionalProperties:false },
    annotations:{ readOnlyHint:false, untrustedContentHint:false },
    execute:async (input) => {
      const id = (input as { backtestId?:unknown })?.backtestId;
      if (typeof id !== "string" || !/^[0-9a-f-]{36}$/i.test(id)) throw new Error("A valid backtestId is required.");
      await api.delete(id); window.dispatchEvent(new Event("quantlab:backtests-changed"));
      return { backtestId:id, deleted:true };
    },
  }, { signal:lifecycle.signal })).catch(() => undefined);
  return () => lifecycle.abort();
}

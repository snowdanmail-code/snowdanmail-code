package org.example.vpnvisibility;
import java.lang.reflect.Array;
import java.lang.reflect.Method;
import de.robv.android.xposed.IXposedHookLoadPackage;
import de.robv.android.xposed.XC_MethodHook;
import de.robv.android.xposed.XposedBridge;
import de.robv.android.xposed.XposedHelpers;
import de.robv.android.xposed.callbacks.XC_LoadPackage;

/** Scoped LSPosed hooks. Never enable for core Android or system processes. */
public final class VpnVisibilityHook implements IXposedHookLoadPackage {
  static final int TRANSPORT_VPN=4, NET_CAPABILITY_NOT_VPN=15, TYPE_VPN=17;
  @Override public void handleLoadPackage(XC_LoadPackage.LoadPackageParam lp) {
    if (lp==null || lp.packageName==null) return;
    String p=lp.packageName;
    if ("android".equals(p)||"system".equals(p)||p.startsWith("com.android.")||
        p.startsWith("com.google.android.")||p.startsWith("com.samsung.android.")||
        p.equals("org.example.vpnvisibility")) return;
    hookCapabilities();
    hookConnectivity();
    XposedBridge.log("VPNVisibility: scoped hooks for "+p);
  }
  private static void hookCapabilities() {
    try {
      Class<?> caps=Class.forName("android.net.NetworkCapabilities");
      XposedHelpers.findAndHookMethod(caps,"hasTransport",int.class,new XC_MethodHook(){
        @Override protected void beforeHookedMethod(MethodHookParam p) {
          if (p.args[0] instanceof Integer && ((Integer)p.args[0])==TRANSPORT_VPN) p.setResult(false);
        }
      });
      XposedHelpers.findAndHookMethod(caps,"hasCapability",int.class,new XC_MethodHook(){
        @Override protected void beforeHookedMethod(MethodHookParam p) {
          if (p.args[0] instanceof Integer && ((Integer)p.args[0])==NET_CAPABILITY_NOT_VPN) p.setResult(true);
        }
      });
      XposedHelpers.findAndHookMethod(caps,"getTransportTypes",new XC_MethodHook(){
        @Override protected void afterHookedMethod(MethodHookParam p) {
          Object v=p.getResult();
          if (!(v instanceof int[])) return;
          int[] a=(int[])v;
          int count=0;
          for(int x:a) if(x!=TRANSPORT_VPN) count++;
          if(count==a.length) return;
          int[] b=new int[count]; int j=0;
          for(int x:a) if(x!=TRANSPORT_VPN) b[j++]=x;
          p.setResult(b);
        }
      });
    } catch (Throwable e) { XposedBridge.log("VPNVisibility capabilities: "+e); }
  }
  private static void hookConnectivity() {
    try {
      Class<?> cm=Class.forName("android.net.ConnectivityManager");
      XposedHelpers.findAndHookMethod(cm,"getNetworkInfo",int.class,new XC_MethodHook(){
        @Override protected void beforeHookedMethod(MethodHookParam p) {
          if (p.args[0] instanceof Integer && ((Integer)p.args[0])==TYPE_VPN) p.setResult(null);
        }
      });
    } catch(Throwable e) { XposedBridge.log("VPNVisibility getNetworkInfo: "+e); }
    try {
      Class<?> cm=Class.forName("android.net.ConnectivityManager");
      XposedHelpers.findAndHookMethod(cm,"getAllNetworkInfo",new XC_MethodHook(){
        @Override protected void afterHookedMethod(MethodHookParam p) {
          Object v=p.getResult();
          if(v==null||!v.getClass().isArray()) return;
          int n=Array.getLength(v), kept=0;
          for(int i=0;i<n;i++) if(!isVpnInfo(Array.get(v,i))) kept++;
          if(kept==n) return;
          Object res=Array.newInstance(v.getClass().getComponentType(),kept);
          int j=0;
          for(int i=0;i<n;i++) {
            Object item=Array.get(v,i);
            if(!isVpnInfo(item)) Array.set(res,j++,item);
          }
          p.setResult(res);
        }
      });
    } catch(Throwable e) { XposedBridge.log("VPNVisibility getAllNetworkInfo: "+e); }
  }
  static boolean isVpnInfo(Object item) {
    if(item==null) return false;
    try { Method m=item.getClass().getMethod("getType"); return Integer.valueOf(TYPE_VPN).equals(m.invoke(item)); }
    catch(Throwable ignored) { return false; }
  }
}

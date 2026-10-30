package de.robv.android.xposed;
public abstract class XC_MethodHook {
  protected void beforeHookedMethod(MethodHookParam p) throws Throwable {}
  protected void afterHookedMethod(MethodHookParam p) throws Throwable {}
  public static class Unhook {}
  public static class MethodHookParam {
    public Object[] args;
    public Object getResult(){ throw new UnsupportedOperationException(); }
    public void setResult(Object x){ throw new UnsupportedOperationException(); }
  }
}

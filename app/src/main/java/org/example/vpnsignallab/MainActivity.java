package org.example.vpnsignallab;

import android.Manifest;
import android.app.Activity;
import android.app.AppOpsManager;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.Build;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.View;
import android.widget.*;
import java.net.NetworkInterface;
import java.util.*;

public final class MainActivity extends Activity {
  private static final int BG=Color.rgb(15,23,38), FG=Color.WHITE, DIM=Color.rgb(189,200,217), BLUE=Color.rgb(50,115,220);
  private final ArrayList<AppInfo> apps=new ArrayList<>(), shown=new ArrayList<>();
  private final HashSet<String> selected=new HashSet<>();
  private PackageManager pm;
  private SharedPreferences prefs;
  private ListView list;
  private ArrayAdapter<String> adapter;
  private TextView netText, chosenText;
  private String currentReport="";
  private static class AppInfo {
    final String name, pkg;
    AppInfo(String n,String p){name=n;pkg=p;}
  }
  private int dp(int x){return Math.round(x*getResources().getDisplayMetrics().density);}
  private GradientDrawable bg(int color){
    GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(12));return d;
  }
  private TextView txt(String v,int size,int color,boolean bold){
    TextView t=new TextView(this);t.setText(v);t.setTextColor(color);t.setTextSize(size);
    t.setLineSpacing(dp(2),1.05f);if(bold)t.setTypeface(Typeface.DEFAULT,Typeface.BOLD);return t;
  }
  private LinearLayout.LayoutParams lp(int height,int top){
    LinearLayout.LayoutParams l=new LinearLayout.LayoutParams(-1,height<0?height:dp(height));l.topMargin=dp(top);return l;
  }
  private Button btn(String label,View.OnClickListener click){
    Button b=new Button(this);b.setText(label);b.setTextColor(FG);b.setTextSize(14);b.setBackground(bg(BLUE));b.setOnClickListener(click);return b;
  }
  @Override public void onCreate(Bundle state){
    super.onCreate(state);
    pm=getPackageManager();prefs=getSharedPreferences("chosen_apps",MODE_PRIVATE);
    selected.addAll(prefs.getStringSet("packages",Collections.emptySet()));
    getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);
    LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);
    root.setPadding(dp(16),dp(12),dp(16),dp(12));root.setBackgroundColor(BG);setContentView(root);
    root.addView(txt("VPN Signal Lab",25,FG,true),lp(-2,2));
    root.addView(txt("Диагностика, а не блокировка VPN · Android 8–16+",12,DIM,false),lp(-2,3));
    netText=txt("Чтение состояния VPN...",14,FG,false);
    netText.setPadding(dp(12),dp(11),dp(12),dp(10));netText.setBackground(bg(Color.rgb(29,41,62)));
    root.addView(netText,lp(-2,13));
    root.addView(btn("Обновить проверку VPN",v->refresh()),lp(46,9));
    root.addView(txt("Тест: при включённом стороннем VPN запиши результат. Затем исключи ТОЛЬКО VPN Signal Lab в настройках этого VPN и обнови данные.",12,DIM,false),lp(-2,9));
    root.addView(txt("Приложения для будущих проверок (без блокировки)",14,FG,true),lp(-2,13));
    EditText search=new EditText(this);
    search.setSingleLine(true);search.setHint("Поиск по имени или пакету");search.setTextColor(FG);
    search.setHintTextColor(DIM);search.setTextSize(14);root.addView(search,lp(44,5));
    chosenText=txt("",12,DIM,false);root.addView(chosenText,lp(-2,5));
    list=new ListView(this);list.setChoiceMode(ListView.CHOICE_MODE_MULTIPLE);
    adapter=new ArrayAdapter<>(this,android.R.layout.simple_list_item_multiple_choice,new ArrayList<String>());
    list.setAdapter(adapter);
    LinearLayout.LayoutParams l=new LinearLayout.LayoutParams(-1,0,1f);l.topMargin=dp(5);root.addView(list,l);
    list.setOnItemClickListener((a,v,pos,id)->{
      if(pos<0||pos>=shown.size())return;
      String p=shown.get(pos).pkg;
      if(list.isItemChecked(pos))selected.add(p);else selected.remove(p);
      prefs.edit().putStringSet("packages",new HashSet<>(selected)).apply();
      chosenText.setText("Выбрано: "+selected.size()+" · найдено: "+shown.size());
    });
    search.addTextChangedListener(new TextWatcher(){
      public void beforeTextChanged(CharSequence s,int start,int count,int after){}
      public void onTextChanged(CharSequence s,int start,int before,int count){filter(s.toString());}
      public void afterTextChanged(Editable e){}
    });
    root.addView(btn("Скопировать диагностический отчёт",v->copy()),lp(48,9));
    root.addView(txt("Без INTERNET-разрешения. VPN и другие приложения не изменяются.",11,DIM,false),lp(-2,8));
    load();refresh();
  }
  private void load(){
    try {
      for(ApplicationInfo a:pm.getInstalledApplications(0)){
        if((a.flags&ApplicationInfo.FLAG_SYSTEM)!=0||a.packageName.equals(getPackageName()))continue;
        CharSequence n=pm.getApplicationLabel(a);
        apps.add(new AppInfo(n==null?a.packageName:n.toString(),a.packageName));
      }
      Collections.sort(apps,Comparator.comparing(a->a.name.toLowerCase(Locale.ROOT)));
    }catch(Exception e){Toast.makeText(this,"Ошибка получения приложений",Toast.LENGTH_LONG).show();}
    filter("");
  }
  private void filter(String q){
    String s=q.toLowerCase(Locale.ROOT).trim();
    shown.clear();adapter.clear();
    for(AppInfo a:apps)if(a.name.toLowerCase(Locale.ROOT).contains(s)||a.pkg.toLowerCase(Locale.ROOT).contains(s)){
      shown.add(a);adapter.add(a.name+" · "+a.pkg);
    }
    adapter.notifyDataSetChanged();list.clearChoices();
    for(int i=0;i<shown.size();i++)if(selected.contains(shown.get(i).pkg))list.setItemChecked(i,true);
    chosenText.setText("Выбрано: "+selected.size()+" · найдено: "+shown.size());
  }
  private void refresh(){
    StringBuilder s=new StringBuilder();
    s.append("Android: ").append(Build.VERSION.RELEASE).append(" (API ").append(Build.VERSION.SDK_INT).append(")");
    s.append("\nУстройство: ").append(Build.MANUFACTURER).append(" ").append(Build.MODEL);
    try{
      ConnectivityManager cm=(ConnectivityManager)getSystemService(Context.CONNECTIVITY_SERVICE);
      Network net=cm==null?null:cm.getActiveNetwork();
      NetworkCapabilities cap=net==null?null:cm.getNetworkCapabilities(net);
      if(cap==null)s.append("\nАктивная сеть: сведения недоступны");
      else{
        s.append("\nTRANSPORT_VPN: ").append(cap.hasTransport(NetworkCapabilities.TRANSPORT_VPN)?"ДА":"НЕТ");
        s.append("\nNET_CAPABILITY_NOT_VPN: ").append(cap.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_VPN)?"ДА":"НЕТ");
        s.append("\nТипы транспорта: ");int[] t=cap.getTransportTypes();
        for(int i=0;i<t.length;i++){if(i>0)s.append(", ");s.append(t[i]);}
        if(t.length==0)s.append("нет");
      }
    }catch(Exception e){s.append("\nОшибка сети: ").append(e.getClass().getSimpleName());}
    try{
      String op=AppOpsManager.permissionToOp(Manifest.permission.ACCESS_NETWORK_STATE);
      s.append("\nAppOp ACCESS_NETWORK_STATE: ").append(op==null?"отсутствует":op);
    }catch(Exception e){s.append("\nAppOps: недоступно");}
    try{
      Enumeration<NetworkInterface> n=NetworkInterface.getNetworkInterfaces();
      ArrayList<String> names=new ArrayList<>();
      while(n!=null&&n.hasMoreElements()){
        String name=n.nextElement().getName();
        if(name.startsWith("tun")||name.startsWith("wg")||name.startsWith("ppp"))names.add(name);
      }
      s.append("\nVPN-подобные интерфейсы: ");
      s.append(names.isEmpty()?"не обнаружены":String.join(", ",names));
    }catch(Exception e){s.append("\nИнтерфейсы недоступны");}
    s.append("\n\nРезультат относится только к VPN Signal Lab, не к ВК.");
    currentReport=s.toString();netText.setText(currentReport);
  }
  private void copy(){
    StringBuilder s=new StringBuilder("VPN Signal Lab v0.1 — диагностический отчёт\n");
    s.append(currentReport).append("\n\nВыбранные приложения (никакой блокировки):\n");
    ArrayList<String> packages=new ArrayList<>(selected);Collections.sort(packages);
    for(String p:packages){
      boolean granted=pm.checkPermission(Manifest.permission.ACCESS_NETWORK_STATE,p)==PackageManager.PERMISSION_GRANTED;
      s.append(p).append(" — ACCESS_NETWORK_STATE: ").append(granted?"выдано":"не выдано").append("\n");
    }
    ClipboardManager clip=(ClipboardManager)getSystemService(Context.CLIPBOARD_SERVICE);
    if(clip!=null)clip.setPrimaryClip(ClipData.newPlainText("VPN Signal Lab",s.toString()));
    Toast.makeText(this,"Отчёт скопирован",Toast.LENGTH_SHORT).show();
  }
}

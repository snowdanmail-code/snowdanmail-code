package org.example.vpnvisibility;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

/** Launcher UI for setup instructions. VPN hooks are installed by LSPosed, not this activity. */
public final class MainActivity extends Activity {
    private static final int BG = Color.rgb(13, 19, 31);
    private static final int PANEL = Color.rgb(26, 36, 52);
    private static final int FG = Color.rgb(244, 248, 255);
    private static final int MUTED = Color.rgb(175, 188, 205);
    private static final int ACCENT = Color.rgb(56, 143, 248);
    private int dp(float n) { return Math.round(n * getResources().getDisplayMetrics().density); }

    private GradientDrawable shape(int color, int radius) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color);
        d.setCornerRadius(dp(radius));
        return d;
    }

    private TextView text(String value, int size, int color, boolean bold) {
        TextView v = new TextView(this);
        v.setText(value);
        v.setTextSize(size);
        v.setTextColor(color);
        v.setLineSpacing(dp(3), 1f);
        if (bold) v.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return v;
    }

    private void addText(LinearLayout parent, String value, int size, int color, boolean bold, int top) {
        TextView v = text(value, size, color, bold);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
        lp.topMargin = dp(top);
        parent.addView(v, lp);
    }

    private Button action(String label, Runnable callback) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextColor(FG);
        b.setTextSize(15);
        b.setBackground(shape(ACCENT, 12));
        b.setOnClickListener(v -> callback.run());
        return b;
    }

    private void openManager() {
        try {
            Intent i = getPackageManager().getLaunchIntentForPackage("org.lsposed.manager");
            if (i != null) {
                startActivity(i);
                return;
            }
        } catch (Exception ignored) {}
        Toast.makeText(this, "LSPosed Manager не найден. Откройте его вручную.", Toast.LENGTH_LONG).show();
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(BG);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(22), dp(28), dp(22), dp(32));
        scroll.addView(root);
        setContentView(scroll);

        TextView logo = text("VPN Visibility", 27, FG, true);
        root.addView(logo);
        addText(root, "Экспериментальный LSPosed-модуль • v0.2", 14, MUTED, false, 4);

        LinearLayout info = new LinearLayout(this);
        info.setOrientation(LinearLayout.VERTICAL);
        info.setPadding(dp(18), dp(16), dp(18), dp(18));
        info.setBackground(shape(PANEL, 16));
        LinearLayout.LayoutParams card = new LinearLayout.LayoutParams(-1, -2);
        card.topMargin = dp(26);
        root.addView(info, card);
        addText(info, "Как это работает", 18, FG, true, 0);
        addText(info, "Сам VPN остаётся активным. Модуль меняет ответы отдельных Android API только в выбранных приложениях.", 15, MUTED, false, 11);
        addText(info, "Для работы обязательны root и совместимый LSPosed. Значок приложения не означает, что модуль активен.", 15, Color.rgb(255, 198, 102), false, 14);

        addText(root, "Активация", 20, FG, true, 26);
        addText(root, "1. Откройте LSPosed Manager.", 15, FG, false, 16);
        addText(root, "2. Включите модуль VPN Visibility.", 15, FG, false, 10);
        addText(root, "3. В области действия (Scope) отметьте ВКонтакте: com.vkontakte.android.", 15, FG, false, 10);
        addText(root, "4. Полностью закройте и запустите ВК заново.", 15, FG, false, 10);

        Button manager = action("Открыть LSPosed Manager", this::openManager);
        LinearLayout.LayoutParams managerLp = new LinearLayout.LayoutParams(-1, dp(54));
        managerLp.topMargin = dp(25);
        root.addView(manager, managerLp);

        Button copy = action("Скопировать пакет ВК", () -> {
            ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            if (clipboard != null) clipboard.setPrimaryClip(ClipData.newPlainText("VK package", "com.vkontakte.android"));
            Toast.makeText(this, "com.vkontakte.android скопирован", Toast.LENGTH_SHORT).show();
        });
        copy.setBackground(shape(PANEL, 12));
        LinearLayout.LayoutParams copyLp = new LinearLayout.LayoutParams(-1, dp(54));
        copyLp.topMargin = dp(12);
        root.addView(copy, copyLp);

        addText(root, "Ограничение: модуль не скрывает внешний VPN-IP, DNS и проверки вне перехваченных API. Работа с конкретной версией ВК не подтверждена.", 13, MUTED, false, 25);
    }
}

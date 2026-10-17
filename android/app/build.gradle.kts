plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.example.airemote"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.example.airemote"
        minSdk = 29
        targetSdk = 35
        versionCode = 31
        versionName = "2.11.0-persistent-stop"
        buildConfigField("boolean", "EXTERNAL_GAME_ACTIONS_ENABLED", "false")
    }
    buildFeatures { buildConfig = true }
    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}


dependencies {
    testImplementation("junit:junit:4.13.2")
}

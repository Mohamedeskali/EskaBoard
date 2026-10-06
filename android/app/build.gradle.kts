plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// Release signing comes from the environment (GitHub Actions secrets, see README).
// Without it, only the debug APK can be built.
val keystoreFile = System.getenv("ESKABOARD_KEYSTORE")?.takeIf { it.isNotBlank() }?.let(::file)

android {
    namespace = "org.eskaboard.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "org.eskaboard.app"
        minSdk = 24
        targetSdk = 35
        // CI sets these so each build installs over the previous one
        versionCode = System.getenv("ESKABOARD_VERSION_CODE")?.toIntOrNull() ?: 1
        versionName = System.getenv("ESKABOARD_VERSION_NAME")?.takeIf { it.isNotBlank() } ?: "1.0"
    }

    signingConfigs {
        if (keystoreFile != null) {
            create("release") {
                storeFile = keystoreFile
                storePassword = System.getenv("ESKABOARD_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("ESKABOARD_KEY_ALIAS")
                keyPassword = System.getenv("ESKABOARD_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.findByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.activity:activity-ktx:1.9.3")
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("com.journeyapps:zxing-android-embedded:4.3.0")

    testImplementation("junit:junit:4.13.2")
}

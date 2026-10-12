plugins {
  id("com.android.application")
  id("org.jetbrains.kotlin.android")
}

android {
  namespace = "ai.lifesnap.capture"
  compileSdk = 35

  defaultConfig {
    applicationId = "ai.lifesnap.capture"
    minSdk = 26
    targetSdk = 35
    versionCode = 1
    versionName = "0.1.0"
    val defaultUrl = providers.gradleProperty("lifeSnapBaseUrl").orElse("http://10.0.2.2:8023").get()
    buildConfigField("String", "DEFAULT_BACKEND_URL", "\"$defaultUrl\"")
  }

  buildFeatures {
    buildConfig = true
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
  implementation("androidx.core:core-ktx:1.15.0")
}

plugins {
    alias(libs.plugins.kotlinMultiplatform)
    alias(libs.plugins.androidLibrary)
}

kotlin {
    androidTarget {
        compilations.all {
            kotlinOptions {
                jvmTarget = "17"
            }
        }
    }
    
    jvm("desktop") {
        compilations.all {
            kotlinOptions {
                jvmTarget = "17"
            }
        }
    }

    sourceSets {
        commonMain.dependencies {
            implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.8.0")
            implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")
            implementation("org.jetbrains.kotlinx:kotlinx-datetime:0.5.0")
        }
        
        androidMain.dependencies {
            // Google MediaPipe GenAI / LiteRT LLM Inference SDK
            implementation("com.google.mediapipe:tasks-genai:0.10.14")
            implementation("androidx.annotation:annotation:1.7.1")
        }
        
        val desktopMain by getting {
            dependencies {
                implementation("com.squareup.okhttp3:okhttp:4.12.0")
            }
        }
    }
}

android {
    namespace = "org.openhealthstack.edgeslm"
    compileSdk = 34
    defaultConfig {
        minSdk = 26
    }
}

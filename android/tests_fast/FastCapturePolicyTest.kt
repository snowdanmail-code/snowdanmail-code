import com.example.airemote.FastCapturePolicy

fun main() {
    check(FastCapturePolicy.shouldUpload(2,1,1000,1100,0,true))
    check(!FastCapturePolicy.shouldUpload(1,1,1000,1100,0,true))
    check(!FastCapturePolicy.shouldUpload(2,1,1000,2400,0,true))
    check(!FastCapturePolicy.shouldUpload(2,1,1200,1100,0,true))
    check(!FastCapturePolicy.shouldUpload(2,1,1300,1600,1300,true))
    check(FastCapturePolicy.shouldUpload(3,2,1400,1900,1300,true))
    check(!FastCapturePolicy.shouldUpload(3,2,1400,1900,1300,false))
    println("7 Kotlin frame-selection checks passed")
}

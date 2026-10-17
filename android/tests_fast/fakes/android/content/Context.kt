package android.content

/** Minimal fake for isolated Kotlin JVM tests ONLY; never added to Android production source. */
open class Context(private val data: MutableMap<String, Boolean>) {
    companion object { const val MODE_PRIVATE = 0 }
    fun getSharedPreferences(name: String, mode: Int): FakePrefs {
        require(mode == MODE_PRIVATE)
        return FakePrefs(name, data)
    }
}

class FakePrefs(private val name: String, private val data: MutableMap<String, Boolean>) {
    fun getBoolean(key: String, fallback: Boolean): Boolean = data["$name:$key"] ?: fallback
    fun edit(): Editor = Editor(name, data)
    class Editor(private val name: String, private val data: MutableMap<String, Boolean>) {
        private val pending = mutableMapOf<String, Boolean>()
        fun putBoolean(key: String, value: Boolean): Editor { pending["$name:$key"] = value; return this }
        fun commit(): Boolean { data.putAll(pending); return true }
    }
}

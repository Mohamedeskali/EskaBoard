package org.eskaboard.app

import org.junit.Assert.assertEquals
import org.junit.Test

class AppSettingsTest {
    @Test
    fun pageJsonHasTheLanguageAndHiddenTools() {
        assertEquals("""{"lang":"","hidden":[]}""", AppSettings.pageJson("", emptySet()))
        assertEquals(
            """{"lang":"fr","hidden":["esc","paste","shots"]}""",
            AppSettings.pageJson("fr", setOf("shots", "esc", "paste")), // in toolbar order
        )
    }

    @Test
    fun unknownValuesNeverReachThePage() {
        assertEquals(
            """{"lang":"","hidden":["copy"]}""",
            AppSettings.pageJson("x\"});alert(1)//", setOf("copy", "\"]}", "unknown")),
        )
    }

    @Test
    fun toolNamesMatchThePage() {
        // data-tool values in phonekb/static/index.html
        assertEquals(listOf("enter", "esc", "erase", "copy", "paste", "shots"), AppSettings.TOOLS)
    }
}

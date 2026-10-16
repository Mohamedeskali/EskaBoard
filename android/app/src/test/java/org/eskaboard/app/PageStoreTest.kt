package org.eskaboard.app

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PageStoreTest {
    @Test
    fun acceptsKnownNames() {
        assertTrue(PageStore.accepts("history", "[]"))
        assertTrue(PageStore.accepts("draft", ""))
    }

    @Test
    fun refusesOtherNames() {
        assertFalse(PageStore.accepts("settings", "x"))
        assertFalse(PageStore.accepts("", "x"))
    }

    @Test
    fun refusesTooLong() {
        assertFalse(PageStore.accepts("draft", "x".repeat(PageStore.MAX_LENGTH + 1)))
    }
}

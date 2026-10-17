package com.example.airemote

fun main() {
    var count = 0
    fun checkOne(value: Boolean) { check(value); count++ }
    val control = OperatorControl()
    checkOne(control.mayStart())
    checkOne(!control.isStopped())
    checkOne(control.stop())
    checkOne(control.isStopped())
    checkOne(!control.mayStart())
    checkOne(!control.stop())
    control.resetByOperator()
    checkOne(control.mayStart())
    val latched = OperatorControl(true)
    checkOne(latched.isStopped())
    checkOne(!latched.mayStart())
    println("OperatorControl: $count checks PASSED")
}

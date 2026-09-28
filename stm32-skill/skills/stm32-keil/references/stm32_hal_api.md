# STM32F4 HAL API Patterns (AC5, this board)

Clock baseline for skill examples: **HSI 16 MHz, PLL off** (SYSCLK/AHB 16 MHz,
APB1 4 MHz, APB2 8 MHz, flash latency 0). HSE 8 MHz + PLL 168 MHz is possible
but unverified on this board; prefer HSI unless HSE is confirmed.

## Clock tree quick reference (HSI path)

- `HAL_RCC_OscConfig`: HSI on, PLL none.
- `HAL_RCC_ClockConfig`: SYSCLK=HSI, AHB=/1, APB1=/4, APB2=/2, latency FLASH_LATENCY_0.
- Timer clock: when APB prescaler != 1, the timer clock = APBx_clk * 2.
  On HSI path: APB1=4 MHz -> timer clock 8 MHz; APB2=8 MHz -> 8 MHz.

## GPIO

```c
__HAL_RCC_GPIOA_CLK_ENABLE();
GPIO_InitTypeDef g = {0};
g.Pin = GPIO_PIN_0;
g.Mode = GPIO_MODE_OUTPUT_PP;
g.Pull = GPIO_NOPULL;
g.Speed = GPIO_SPEED_FREQ_LOW;
HAL_GPIO_Init(GPIOA, &g);
HAL_GPIO_WritePin(GPIOA, GPIO_PIN_0, GPIO_PIN_SET);   // high
HAL_GPIO_TogglePin(GPIOA, GPIO_PIN_0);
```

- Input (button): `g.Mode = GPIO_MODE_INPUT;` rely on external pull-up.
- EXTI: `GPIO_MODE_IT_FALLING`, then `HAL_NVIC_SetPriority(EXTI0_IRQn,..)` /
  `HAL_NVIC_EnableIRQ`, and implement `EXTI0_IRQHandler` -> `HAL_GPIO_EXTI_IRQHandler`.

## Time base / delays

- `HAL_Init()` configures SysTick (1 kHz). Implement `SysTick_Handler` ->
  `HAL_IncTick()`. Use `HAL_Delay(ms)`.
- On this board the example's `main.c` defines `SysTick_Handler` directly.

## UART (USART1, PA9 TX / PA10 RX, 115200 8N1)

```c
__HAL_RCC_USART1_CLK_ENABLE();
__HAL_RCC_GPIOA_CLK_ENABLE();
// PA9 AF7 (TX), PA10 AF7 (RX), alternate function push-pull pull-up.
UART_HandleTypeDef huart1;
huart1.Instance = USART1;
huart1.Init.BaudRate = 115200;
huart1.Init.WordLength = UART_WORDLENGTH_8B;
huart1.Init.StopBits = UART_STOPBITS_1;
huart1.Init.Parity = UART_PARITY_NONE;
huart1.Init.Mode = UART_MODE_TX_RX;
huart1.Init.HwFlowCtl = UART_HWCONTROL_NONE;
HAL_UART_Init(&huart1);
```

- Send: `HAL_UART_Transmit(&huart1, (uint8_t*)str, len, timeout)`.
- Receive (interrupt): `HAL_UART_Receive_IT(&huart1, &byte, 1)` and override
  `HAL_UART_RxCpltCallback`.

### printf retarget

With the **standard library** (MicroLIB off, as in these examples), retarget
`fputc`:

```c
int fputc(int ch, FILE *f) {
    HAL_UART_Transmit(&huart1, (uint8_t*)&ch, 1, 0xFFFF);
    return ch;
}
```

With MicroLIB the retarget uses `#if !defined(OS_USE_SEMIHOSTING)` /
`PUTCHAR_PROTOTYPE`. Match the project's library (see check report: MicroLIB).

## TIM / PWM

- Use a timer channel in PWM mode. On the board, PA1 (backlight D2) is TIM2_CH2
  on F407? Verify in the device header; the TFT backlight PB1 = TIM3_CH4.
- Sequence: enable timer clock -> set prescaler/period -> set compare mode ->
  `HAL_TIM_PWM_Start(&htim, TIM_CHANNEL_x)`. Duty = compare / (period+1).
- On HSI path timer clock = 8 MHz; pick PSC/ARR for the desired frequency.

```c
htim.Init.Prescaler = psc;
htim.Init.Period = arr;
HAL_TIM_PWM_Init(&htim, ...);
__HAL_TIM_SET_COMPARE(&htim, TIM_CHANNEL_x, duty);
```

## ADC / I2C / SPI / USB

- ADC: single conversion on a channel; set resolution 12-bit, sample time.
- I2C1 on PB6/PB7 (board routed). Use 4.7k pull-ups externally.
- SPI1 conflicts with the on-board W25Qxx (PB3/4/5, PA15). Use SPI2
  (PB13/PB15 with PB12 CS) for external devices to avoid the W25Qxx.
- USB OTG FS on PA11/PA12 (Type-C) requires the USB device stack and PMA
  buffers; do not add it casually (pulls in HAL PCD + USB library).

## NVIC / interrupts

- `HAL_NVIC_SetPriority(IRQn, preempt, sub)` and `HAL_NVIC_EnableIRQ(IRQn)`.
- Keep ISRs short; defer work with flags. The SysTick priority must be the
  lowest used by `HAL_Delay`.

## Pitfalls seen on this board

- Forgetting `SysTick_Handler` -> `HAL_IncTick` makes `HAL_Delay` hang forever.
- HSE on an unproven crystal can leave the chip in `Error_Handler`; start on
  HSI and bring up HSE only after UART/LED prove the core runs.

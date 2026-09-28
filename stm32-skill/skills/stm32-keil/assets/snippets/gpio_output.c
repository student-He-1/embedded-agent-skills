/* gpio_output.c — minimal push-pull GPIO output pattern (HAL, F407).
 * Copy into your project's init, then drive with HAL_GPIO_WritePin / Toggle. */

#include "main.h"

/* Call once for the whole GPIOA bank, then configure individual pins. */
void led_pin_init(GPIO_TypeDef *port, uint16_t pin)
{
    if (port == GPIOA) __HAL_RCC_GPIOA_CLK_ENABLE();
    else if (port == GPIOB) __HAL_RCC_GPIOB_CLK_ENABLE();
    /* add GPIOC..GPIOK as needed */

    GPIO_InitTypeDef g = {0};
    g.Pin = pin;
    g.Mode = GPIO_MODE_OUTPUT_PP;
    g.Pull = GPIO_NOPULL;
    g.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(port, &g);
    HAL_GPIO_WritePin(port, pin, GPIO_PIN_RESET);
}

/* usage:
 *   led_pin_init(GPIOA, GPIO_PIN_0);
 *   HAL_GPIO_WritePin(GPIOA, GPIO_PIN_0, GPIO_PIN_SET);   // on
 *   HAL_GPIO_TogglePin(GPIOA, GPIO_PIN_0);
 *
 * Input button example:
 *   g.Mode = GPIO_MODE_INPUT;  // rely on external pull-up (S1=PA0)
 */

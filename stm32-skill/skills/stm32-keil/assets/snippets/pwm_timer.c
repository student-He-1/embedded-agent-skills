/* pwm_timer.c — TIM PWM output pattern (HAL, F407).
 * Example: TIM2_CH2 on PA1 (AF1). Tune PSC/ARR for your desired frequency. */

#include "main.h"

TIM_HandleTypeDef htim2;

/* Timer clock on HSI path = 8 MHz (APB1 4 MHz * 2).
 * PSC=7 -> 1 MHz tick; ARR=999 -> 1 kHz PWM on the LED. */
void pwm_init(void)
{
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_TIM2_CLK_ENABLE();

    GPIO_InitTypeDef g = {0};
    g.Pin = GPIO_PIN_1;                 /* TIM2_CH2 */
    g.Mode = GPIO_MODE_AF_PP;
    g.Pull = GPIO_NOPULL;
    g.Speed = GPIO_SPEED_FREQ_LOW;
    g.Alternate = GPIO_AF1_TIM2;
    HAL_GPIO_Init(GPIOA, &g);

    htim2.Instance = TIM2;
    htim2.Init.Prescaler = 8 - 1U;
    htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim2.Init.Period = 1000 - 1U;
    htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;
    HAL_TIM_Base_Init(&htim2);

    TIM_OC_InitTypeDef oc = {0};
    oc.OCMode = TIM_OCMODE_PWM1;
    oc.Pulse = 0;
    oc.OCPolarity = TIM_OCPOLARITY_HIGH;
    oc.OCFastMode = TIM_OCFAST_DISABLE;
    HAL_TIM_PWM_ConfigChannel(&htim2, &oc, TIM_CHANNEL_2);

    HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_2);
}

/* Set duty 0..ARR (0..999 here). */
void pwm_set_duty(uint32_t duty)
{
    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_2, duty);
}
